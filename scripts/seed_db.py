"""
scripts/seed_db.py
------------------
Load the committed JSON catalogue into PostgreSQL.

Idempotent: every row is upserted by primary key, and published photos that
no longer exist in `photo_attribution.json` are removed, so re-running after
a content change converges instead of duplicating.

USAGE
-----
  python scripts/seed_db.py                 # upsert everything
  python scripts/seed_db.py --if-empty      # no-op when landmarks exist (container boot)
  python scripts/seed_db.py --check         # verify row counts only, change nothing

Reads DATABASE_URL from the environment (same variable as the API).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.constants import CLASS_LANDMARK_ALIASES, UNVALIDATED_CLASSES  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
PHOTOS_DIR = DATA_DIR / "photos"
SPLIT_MANIFEST = DATA_DIR / "images_v2" / "manifests" / "split.json"

EXPECTED_LANDMARKS = 46
EXPECTED_CLASSES = 29
EXPECTED_PUBLISHED_PHOTOS = 38


def load_json(path: Path):
    if not path.exists():
        raise SystemExit(f"Missing input file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalise_path(raw: str | None, landmark_id: str) -> str:
    """Return the path as stored in the repository, independent of Windows slashes."""
    if raw:
        cleaned = raw.replace("\\", "/")
        if cleaned.startswith("data/"):
            return cleaned
    matches = sorted(PHOTOS_DIR.glob(f"{landmark_id}.*"))
    if not matches:
        return f"data/photos/{landmark_id}.jpg"
    return f"data/photos/{matches[0].name}"


def sha256_of(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_counts() -> dict[str, dict[str, int]]:
    """Per-class image counts per split, from the committed manifest."""
    counts: dict[str, dict[str, int]] = {}
    if not SPLIT_MANIFEST.exists():
        return counts
    for item in load_json(SPLIT_MANIFEST):
        cls = item.get("cls")
        split = item.get("split")
        if not cls or split not in {"train", "val", "test"}:
            continue
        bucket = counts.setdefault(cls, {"train": 0, "val": 0, "test": 0})
        bucket[split] += 1
    return counts


def build_rows():
    catalogue = load_json(DATA_DIR / "landmarks.json")["landmarks"]
    attribution = load_json(DATA_DIR / "photo_attribution.json")
    sources = load_json(DATA_DIR / "photo_sources.json")
    class_names = load_json(MODELS_DIR / "class_names.json")
    counts = split_counts()

    landmark_ids = {lm["id"] for lm in catalogue}
    missing = [
        name for name in class_names
        if name not in landmark_ids and CLASS_LANDMARK_ALIASES.get(name) not in landmark_ids
    ]
    if missing:
        raise SystemExit(f"Model classes with no landmark record: {missing}")

    landmarks = []
    for order, lm in enumerate(catalogue):
        landmarks.append(
            (
                lm["id"],
                lm["name"],
                lm.get("name_ru"),
                lm.get("address"),
                lm.get("year_built"),
                lm.get("type"),
                lm.get("style"),
                lm.get("architect"),
                lm.get("description"),
                lm.get("fun_fact"),
                lm.get("lat"),
                lm.get("lon"),
                lm.get("coordinate_source"),
                lm.get("angles") or [],
                Jsonb(lm.get("photos") or []),
                order,
            )
        )

    photos = []
    for landmark_id, item in attribution.items():
        if not item.get("published"):
            continue
        if landmark_id not in landmark_ids:
            raise SystemExit(f"Attribution for unknown landmark: {landmark_id}")
        stored = PHOTOS_DIR / f"{landmark_id}.jpg"
        source = sources.get(landmark_id) or {}
        pixels = source.get("pixels") or {}
        photos.append(
            (
                f"{landmark_id}_01",
                landmark_id,
                item.get("file") or source.get("filename"),
                normalise_path(item.get("thumbnail"), landmark_id),
                sha256_of(stored),
                "image/jpeg",
                pixels.get("width"),
                pixels.get("height"),
                item.get("author"),
                item.get("license"),
                item.get("license_url"),
                item.get("source"),
                item.get("source_url"),
            )
        )

    classes = []
    for index, name in enumerate(class_names):
        per_split = counts.get(name, {})
        landmark_id = name if name in landmark_ids else CLASS_LANDMARK_ALIASES.get(name)
        note = None
        if landmark_id and landmark_id != name:
            note = (
                "Merged training class: images of kramer_mansion (114) and "
                "kramer_revenue_house (116) share this label; the mansion is "
                "the representative landmark record."
            )
        classes.append(
            (
                name,
                landmark_id,
                index,
                name not in UNVALIDATED_CLASSES,
                note,
                per_split.get("train", 0),
                per_split.get("val", 0),
                per_split.get("test", 0),
            )
        )

    return landmarks, photos, classes


def upsert(conn: psycopg.Connection, landmarks, photos, classes) -> None:
    # psycopg opens a transaction on first execute and commits when the
    # connection context exits, so all three upserts land atomically.
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO landmarks (
                id, name, name_ru, address, year_built, building_type, style,
                architect, description, fun_fact, lat, lon, coordinate_source,
                angles, source_photos, sort_order
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                name_ru = EXCLUDED.name_ru,
                address = EXCLUDED.address,
                year_built = EXCLUDED.year_built,
                building_type = EXCLUDED.building_type,
                style = EXCLUDED.style,
                architect = EXCLUDED.architect,
                description = EXCLUDED.description,
                fun_fact = EXCLUDED.fun_fact,
                lat = EXCLUDED.lat,
                lon = EXCLUDED.lon,
                coordinate_source = EXCLUDED.coordinate_source,
                angles = EXCLUDED.angles,
                source_photos = EXCLUDED.source_photos,
                sort_order = EXCLUDED.sort_order
            """,
            landmarks,
        )

        cur.executemany(
            """
            INSERT INTO photos (
                id, landmark_id, filename, stored_path, sha256, mime,
                width, height, author, license, license_url, source,
                source_url, is_published, verified_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, now())
            ON CONFLICT (id) DO UPDATE SET
                landmark_id = EXCLUDED.landmark_id,
                filename = EXCLUDED.filename,
                stored_path = EXCLUDED.stored_path,
                sha256 = EXCLUDED.sha256,
                mime = EXCLUDED.mime,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                author = EXCLUDED.author,
                license = EXCLUDED.license,
                license_url = EXCLUDED.license_url,
                source = EXCLUDED.source,
                source_url = EXCLUDED.source_url,
                is_published = true,
                verified_at = now()
            """,
            photos,
        )

        cur.executemany(
            """
            INSERT INTO model_classes (
                class_name, landmark_id, class_index, is_validated,
                mapping_note, train_images, val_images, test_images
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (class_name) DO UPDATE SET
                landmark_id = EXCLUDED.landmark_id,
                class_index = EXCLUDED.class_index,
                is_validated = EXCLUDED.is_validated,
                mapping_note = EXCLUDED.mapping_note,
                train_images = EXCLUDED.train_images,
                val_images = EXCLUDED.val_images,
                test_images = EXCLUDED.test_images
            """,
            classes,
        )

        # Drop photos that were unpublished or re-sourced since the last seed.
        keep = [row[0] for row in photos]
        cur.execute(
            "DELETE FROM photos WHERE is_published AND NOT (id = ANY(%s))",
            (keep,),
        )


def read_counts(conn: psycopg.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
            (SELECT count(*) FROM landmarks)::int AS landmarks,
            (SELECT count(*) FROM model_classes)::int AS classes,
            (SELECT count(*) FROM photos WHERE is_published)::int AS published_photos,
            (SELECT count(*) FROM photos
              WHERE is_published AND author IS NOT NULL)::int AS credited_photos
        """
    ).fetchone()
    return {
        "landmarks": row[0],
        "classes": row[1],
        "published_photos": row[2],
        "credited_photos": row[3],
    }


def check(conn: psycopg.Connection) -> int:
    counts = read_counts(conn)
    expected = {
        "landmarks": EXPECTED_LANDMARKS,
        "classes": EXPECTED_CLASSES,
        "published_photos": EXPECTED_PUBLISHED_PHOTOS,
        "credited_photos": EXPECTED_PUBLISHED_PHOTOS,
    }
    problems = []
    for key, want in expected.items():
        got = counts[key]
        status = "ok" if got == want else "MISMATCH"
        print(f"  {key:18} {got:>4} (expected {want}) {status}")
        if got != want:
            problems.append(key)
    if problems:
        print(f"Seed check failed: {', '.join(problems)}", file=sys.stderr)
        return 1
    print("Seed check passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed PostgreSQL from the JSON catalogue")
    parser.add_argument("--if-empty", action="store_true", help="do nothing when landmarks already exist")
    parser.add_argument("--check", action="store_true", help="verify counts without writing")
    args = parser.parse_args()

    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2

    landmarks, photos, classes = build_rows()

    with psycopg.connect(dsn) as conn:
        if args.check:
            return check(conn)

        if args.if_empty:
            existing = conn.execute("SELECT count(*) FROM landmarks").fetchone()[0]
            if existing:
                print(f"Database already has {existing} landmarks; skipping seed.")
                return 0

        upsert(conn, landmarks, photos, classes)
        print(
            f"Seeded {len(landmarks)} landmarks, {len(photos)} published photos, "
            f"{len(classes)} model classes."
        )
        return check(conn)


if __name__ == "__main__":
    raise SystemExit(main())
