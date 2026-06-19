"""
download_images.py
------------------
Downloads freely licensed images from Wikimedia Commons for each
landmark on Pushkinskaya Street, Rostov-on-Don.

USAGE
-----
  python download_images.py                 # all landmarks, 10 images each
  python download_images.py --n 20          # 20 per landmark
  python download_images.py --id pushkin_monument   # one landmark only
  python download_images.py --dry-run       # show what would be downloaded
  python download_images.py --list          # print landmark IDs and exit

OUTPUT
------
  data/raw/<landmark_id>/   ready for collect_data.py

HOW IT WORKS
------------
  Three-tier search against Wikimedia Commons API:
    1. Category lookup  (most precise — uses curated category map below)
    2. English title search
    3. Russian title search
  All images are Creative Commons licensed (free for research use).

REQUIREMENTS
------------
  pip install requests pillow
"""

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

import requests
from PIL import Image

# ── paths ────────────────────────────────────────────────────────────────────
DATA_DIR       = Path("data")
RAW_DIR        = DATA_DIR / "raw"
LANDMARKS_JSON = DATA_DIR / "landmarks.json"

# ── Wikimedia API ─────────────────────────────────────────────────────────────
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia requires a descriptive User-Agent — replace with your details
HEADERS     = {
    "User-Agent": (
        "PushkinskayaLandmarkApp/1.0 "
        "(https://github.com/your-repo; your@email.com) "
        "Python/requests"
    )
}

# ── image settings ────────────────────────────────────────────────────────────
MIN_WIDTH      = 500    # skip thumbnails smaller than this
MAX_PER_QUERY  = 20     # results per API call
SLEEP_API      = 0.8    # seconds between API calls (be polite)
SLEEP_DL       = 0.3    # seconds between image downloads
IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# ── Wikimedia Commons category map ────────────────────────────────────────────
# Manually curated categories for maximum hit rate.
# Add/edit as needed — find categories at commons.wikimedia.org
CATEGORY_MAP = {
    "pushkin_monument":       ["Monuments to Alexander Pushkin in Rostov-on-Don",
                               "Alexander Pushkin monuments in Russia"],
    "kirov_monument":         ["Monuments to Sergei Kirov", "Rostov-on-Don"],
    "chekhov_monument":       ["Monuments to Anton Chekhov",
                               "Anton Chekhov in Rostov-on-Don"],
    "vysotsky_monument":      ["Monuments to Vladimir Vysotsky"],
    "pushkin_spheres":        ["Pushkinskaya Street (Rostov-on-Don)"],
    "lyre_fountain":          ["Pushkinskaya Street (Rostov-on-Don)"],
    "library_fountain":       ["Don State Public Library"],
    "don_state_library":      ["Don State Public Library",
                               "Donskaya gosudarstvennaya publichnaya biblioteka"],
    "museum_fine_arts":       ["Rostov Regional Museum of Fine Arts",
                               "Rostovskiy oblastnoy muzey izobrazitelnykh iskusstv"],
    "paramonov_mansion_sfeu": ["Paramonov Mansion Rostov-on-Don",
                               "Southern Federal University buildings"],
    "kramer_mansion":         ["Pushkinskaya Street (Rostov-on-Don)"],
    "kramer_revenue_house":   ["Pushkinskaya Street (Rostov-on-Don)"],
    "spielrein_mansion":      ["Sabina Spielrein", "Spielrein House Rostov-on-Don"],
    "zvorykin_house":         ["Pushkinskaya Street (Rostov-on-Don)"],
    "gavala_house":           ["Pushkinskaya Street (Rostov-on-Don)"],
    "suprunov_mansion":       ["Pushkinskaya Street (Rostov-on-Don)"],
    "lashch_revenue_house":   ["Pushkinskaya Street (Rostov-on-Don)"],
    "mnatsakanova_house":     ["Pushkinskaya Street (Rostov-on-Don)"],
    "kushnarev_house":        ["Pushkinskaya Street (Rostov-on-Don)"],
    "reznichenko_house":      ["Pushkinskaya Street (Rostov-on-Don)"],
    "bakulin_house":          ["Pushkinskaya Street (Rostov-on-Don)"],
    "bostrikiny_house":       ["Pushkinskaya Street (Rostov-on-Don)"],
    "literary_figures_house": ["Pushkinskaya Street (Rostov-on-Don)"],
    "annunciation_church":    ["Church of the Annunciation Rostov-on-Don",
                               "Greek churches in Russia"],
    "rostov_medical_university":["Rostov State Medical University"],
    "sfeu_library":           ["Southern Federal University"],
    "memorial_nazi_victims":  ["World War II memorials in Russia",
                               "Rostov-on-Don in World War II"],
    "budyonny_bust":          ["Monuments to Semyon Budyonny"],
    "sholokhov_monument":     ["Monuments to Mikhail Sholokhov",
                               "Mikhail Sholokhov"],
    "lanterns_1904":          ["Pushkinskaya Street (Rostov-on-Don)"],
    "gorky_park_gate":        ["Gorky Park Rostov-on-Don",
                               "Parks in Rostov-on-Don"],
    "cathedral_nativity":     ["Cathedral of the Nativity of the Virgin Mary Rostov-on-Don",
                               "Cathedrals in Rostov-on-Don"],
    "gorky_theater":          ["Gorky Academic Drama Theatre Rostov-on-Don",
                               "Maxim Gorky Academic Drama Theatre"],
    "gorky_theater_fountain": ["Teatralnaya Square Rostov-on-Don"],
    "underground_mosaics":    ["Underground passages in Rostov-on-Don",
                               "Mosaics in Russia"],
    "musical_theater":        ["Rostov Musical Theatre"],
    "vorozhein_house":        ["Pushkinskaya Street (Rostov-on-Don)"],
    "green_boulevard":        ["Pushkinskaya Street (Rostov-on-Don)"],
    "school_49":              ["Pushkinskaya Street (Rostov-on-Don)"],
}


# ── helpers ───────────────────────────────────────────────────────────────────
def load_landmarks() -> list[dict]:
    with open(LANDMARKS_JSON) as f:
        return json.load(f)["landmarks"]


def api_get(params: dict) -> dict:
    """Call Wikimedia API, return JSON or {}."""
    try:
        r = requests.get(COMMONS_API, params=params,
                         headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"      [API error: {e}]")
        return {}


def category_images(category: str, limit: int) -> list[dict]:
    """Return image infos from a Commons category."""
    params = {
        "action":    "query",
        "generator": "categorymembers",
        "gcmtitle":  f"Category:{category}",
        "gcmtype":   "file",
        "gcmlimit":  limit,
        "prop":      "imageinfo",
        "iiprop":    "url|size|mime",
        "format":    "json",
    }
    data = api_get(params)
    return _extract_imageinfo(data)


def search_images(query: str, limit: int) -> list[dict]:
    """Full-text search on Commons file namespace."""
    params = {
        "action":        "query",
        "generator":     "search",
        "gsrnamespace":  6,
        "gsrsearch":     query,
        "gsrlimit":      limit,
        "prop":          "imageinfo",
        "iiprop":        "url|size|mime",
        "format":        "json",
    }
    data = api_get(params)
    return _extract_imageinfo(data)


def _extract_imageinfo(data: dict) -> list[dict]:
    pages = data.get("query", {}).get("pages", {})
    results = []
    for page in pages.values():
        ii = page.get("imageinfo", [])
        if not ii:
            continue
        info = ii[0]
        mime = info.get("mime", "")
        w    = info.get("width", 0)
        if not mime.startswith("image/"):
            continue
        if w < MIN_WIDTH:
            continue
        results.append({
            "url":   info["url"],
            "width": w,
            "height": info.get("height", 0),
        })
    return results


def collect_urls(landmark: dict, n: int) -> list[dict]:
    """Run all three search tiers, deduplicate, return up to n results."""
    lid     = landmark["id"]
    name_en = landmark["name"]
    name_ru = landmark.get("name_ru", "")
    seen    = set()
    found   = []

    def add(results):
        for r in results:
            if r["url"] not in seen and len(found) < n * 2:
                seen.add(r["url"])
                found.append(r)

    # Tier 1 — category
    for cat in CATEGORY_MAP.get(lid, []):
        if len(found) >= n:
            break
        print(f"    📂 category: {cat[:60]}", end=" ")
        res = category_images(cat, MAX_PER_QUERY)
        print(f"→ {len(res)}")
        add(res)
        time.sleep(SLEEP_API)

    # Tier 2 — English search
    if len(found) < n:
        print(f"    🔍 search EN: {name_en[:60]}", end=" ")
        res = search_images(f"{name_en} Rostov-on-Don", MAX_PER_QUERY)
        print(f"→ {len(res)}")
        add(res)
        time.sleep(SLEEP_API)

    # Tier 3 — Russian search
    if len(found) < n and name_ru:
        print(f"    🔍 search RU: {name_ru[:60]}", end=" ")
        res = search_images(f"{name_ru} Ростов-на-Дону", MAX_PER_QUERY)
        print(f"→ {len(res)}")
        add(res)
        time.sleep(SLEEP_API)

    return found[:n]


def url_to_filename(url: str, lid: str, idx: int) -> str:
    ext = Path(url.split("?")[0]).suffix.lower()
    if ext not in IMG_EXTENSIONS:
        ext = ".jpg"
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{lid}_{idx:04d}_{h}{ext}"


def download_one(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if img.width < MIN_WIDTH:
            return False
        img.save(dest, "JPEG", quality=90)
        return True
    except Exception as e:
        print(f"        ✗ {e}")
        return False


def process_landmark(landmark: dict, n: int, dry_run: bool) -> int:
    lid  = landmark["id"]
    dest = RAW_DIR / lid
    dest.mkdir(parents=True, exist_ok=True)

    existing_count = len(list(dest.glob("*.jpg")))
    still_needed   = max(0, n - existing_count)

    if still_needed == 0:
        print(f"    ✅ already have {existing_count} images, skipping")
        return existing_count

    print(f"    Have {existing_count}, need {still_needed} more…")
    candidates = collect_urls(landmark, still_needed)
    print(f"    → {len(candidates)} candidates to download")

    saved = existing_count
    for i, c in enumerate(candidates):
        fname = url_to_filename(c["url"], lid, saved)
        fpath = dest / fname
        if fpath.exists():
            saved += 1
            continue
        if dry_run:
            print(f"      [DRY RUN] {c['url'][:80]}")
            saved += 1
            continue
        ok = download_one(c["url"], fpath)
        if ok:
            saved += 1
            print(f"      ✓ {fname}  ({c['width']}×{c['height']})")
        time.sleep(SLEEP_DL)

    return saved


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Download Wikimedia Commons images for Pushkinskaya Street landmarks."
    )
    parser.add_argument("--n",       type=int,  default=10,
                        help="Target images per landmark (default 10, aim for 50+)")
    parser.add_argument("--id",      type=str,  default=None,
                        help="Process a single landmark ID only")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be downloaded, save nothing")
    parser.add_argument("--list",    action="store_true",
                        help="Print all landmark IDs and exit")
    args = parser.parse_args()

    landmarks = load_landmarks()

    if args.list:
        print(f"\n{'ID':<35} {'Name'}")
        print("─" * 70)
        for lm in landmarks:
            print(f"  {lm['id']:<33} {lm['name']}")
        print(f"\n  Total: {len(landmarks)} landmarks\n")
        sys.exit(0)

    if args.id:
        landmarks = [lm for lm in landmarks if lm["id"] == args.id]
        if not landmarks:
            print(f"❌ No landmark with id '{args.id}'.")
            sys.exit(1)

    print(f"\n📸 Pushkinskaya Street Landmark Image Downloader")
    print(f"   Landmarks : {len(landmarks)}")
    print(f"   Target    : {args.n} images each")
    print(f"   Destination: {RAW_DIR.resolve()}")
    if args.dry_run:
        print(f"   MODE      : DRY RUN — nothing will be saved")
    print()

    totals = {}
    for lm in landmarks:
        print(f"\n  ── {lm['name']}  [{lm['id']}]")
        count = process_landmark(lm, args.n, args.dry_run)
        totals[lm["id"]] = count

    # summary table
    print(f"\n\n{'─'*60}")
    print(f"  {'Landmark':<38} {'Saved':>6}  {'Target':>6}")
    print(f"{'─'*60}")
    grand = 0
    for lm in landmarks:
        c = totals[lm["id"]]
        ok = "✅" if c >= args.n else "⚠️ "
        print(f"  {ok} {lm['name'][:36]:<36} {c:>6}  {args.n:>6}")
        grand += c
    print(f"{'─'*60}")
    print(f"  {'TOTAL':<38} {grand:>6}")
    print(f"\n✅ Done.\n")
    print(f"Next steps:")
    print(f"  python collect_data.py")
    print(f"  python train.py\n")


if __name__ == "__main__":
    main()
