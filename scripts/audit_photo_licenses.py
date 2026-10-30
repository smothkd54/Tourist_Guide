"""
scripts/audit_photo_licenses.py
-------------------------------
Verify that every thumbnail the site publishes has a known author, licence and
source, and write that provenance to data/photo_attribution.json.

Why this exists
---------------
The project may only publish photos whose author, licence and source are
recorded. data/photo_sources.json says which Wikimedia Commons file each
thumbnail came from, but not who made it or under what licence. Both live in
the file's extmetadata, which this script fetches.

USAGE
-----
  python scripts/audit_photo_licenses.py

Exit code is non-zero if any published photo cannot be attributed, so CI can
refuse to ship a build with an unlicensed image.
"""

import html
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "data" / "photo_sources.json"
OUTPUT_PATH = ROOT / "data" / "photo_attribution.json"
PHOTOS_DIR = ROOT / "data" / "photos"

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "PushkinskayaGuide/0.1 (educational landmark guide; contact: project owner)"
TAG_RE = re.compile(r"<[^>]+>")

# Licences that allow redistribution with attribution. Anything else is a
# publishing blocker, not a warning.
FREE_LICENCE_MARKERS = (
    "cc0", "cc by", "cc-by", "public domain", "pd-", "attribution",
)


def clean(value: str) -> str:
    """Turn the HTML snippets Commons returns into one readable line."""
    text = TAG_RE.sub("", value or "")
    text = html.unescape(text)
    return " ".join(text.split())


def fetch_metadata(filenames: list[str]) -> dict:
    """Return {filename: extmetadata} for up to 50 files per request."""
    out = {}
    for start in range(0, len(filenames), 50):
        batch = filenames[start:start + 50]
        params = {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "extmetadata|url",
            "iiextmetadatafilter": (
                "Artist|LicenseShortName|LicenseUrl|Credit|UsageTerms|"
                "AttributionRequired|CanonicalURL"
            ),
            "titles": "|".join(f"File:{name}" for name in batch),
        }
        resp = requests.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", "")
            filename = title.removeprefix("File:")
            info = (page.get("imageinfo") or [{}])[0]
            out[filename] = info.get("extmetadata", {})
    return out


def main() -> int:
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    published = {p.stem for p in PHOTOS_DIR.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")}

    filenames = [entry["filename"] for entry in sources.values()]
    metadata = fetch_metadata(filenames)

    attribution = {}
    problems = []
    for landmark_id, entry in sorted(sources.items()):
        filename = entry["filename"]
        meta = metadata.get(filename, {})

        def field(name: str) -> str:
            return clean(meta.get(name, {}).get("value", ""))

        author = field("Artist") or field("Credit")
        licence = field("LicenseShortName") or field("UsageTerms")
        licence_url = field("LicenseUrl")
        source_url = field("CanonicalURL") or entry.get("url", "")

        record = {
            "landmark_id": landmark_id,
            "file": filename,
            "author": author,
            "license": licence,
            "license_url": licence_url,
            "source": "Wikimedia Commons",
            "source_url": source_url,
            "thumbnail": f"data/photos/{landmark_id}.jpg",
            "published": landmark_id in published,
        }
        attribution[landmark_id] = record

        if landmark_id not in published:
            continue
        if not author or not licence or not source_url:
            problems.append(f"{landmark_id}: missing author/licence/source "
                            f"(author={author!r}, licence={licence!r})")
        elif not any(marker in licence.lower() for marker in FREE_LICENCE_MARKERS):
            problems.append(f"{landmark_id}: licence {licence!r} is not a free licence")

    missing_entries = published - set(attribution)
    for landmark_id in sorted(missing_entries):
        problems.append(f"{landmark_id}: published thumbnail has no entry in photo_sources.json")

    OUTPUT_PATH.write_text(json.dumps(attribution, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"photos published      : {len(published)}")
    print(f"entries attributed    : {sum(1 for r in attribution.values() if r['published'])}")
    print(f"written               : {OUTPUT_PATH.relative_to(ROOT)}")

    if problems:
        print("\nUNRESOLVED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("all published photos have author, licence and source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
