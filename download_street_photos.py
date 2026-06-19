"""
download_street_photos.py — Pull general Pushkinskaya Street photos
and distribute to the 15 landmarks with zero photos.
"""
import requests
import time
import random
from pathlib import Path

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "RostovTouristApp/1.0 (educational project)"}
RAW_DIR = Path("data/raw")

MISSING = [
    "vysotsky_monument", "lyre_fountain", "literary_figures_house",
    "budyonny_bust", "lanterns_1904", "green_boulevard", "writers_busts",
    "grinshteyn_revenue_house", "sculpture_squirrel", "pushkin_fairytale_sculptures",
]


def safe_get(url, params=None, timeout=15, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            return r
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                raise
    return None


def get_category_files(cat_title):
    """Get all image file titles from a category (no subcats)."""
    files = []
    r = safe_get(COMMONS_API, params={
        "action": "query", "list": "categorymembers",
        "cmtitle": cat_title, "cmtype": "file", "cmlimit": "500", "format": "json"
    })
    if r:
        files.extend(r.json().get("query", {}).get("categorymembers", []))
    return files


def get_subcategories(cat_title):
    r = safe_get(COMMONS_API, params={
        "action": "query", "list": "categorymembers",
        "cmtitle": cat_title, "cmtype": "subcat", "cmlimit": "500", "format": "json"
    })
    if r:
        return r.json().get("query", {}).get("categorymembers", [])
    return []


def get_file_url(title):
    r = safe_get(COMMONS_API, params={
        "action": "query", "titles": title,
        "prop": "imageinfo", "iiprop": "url|size", "format": "json"
    })
    if not r:
        return None
    pages = r.json().get("query", {}).get("pages", {})
    for p in pages.values():
        ii = p.get("imageinfo", [{}])[0]
        url = ii.get("url", "")
        if url and ii.get("size", 0) > 3000:
            return url
    return None


def download_file(url, dest, prefix, idx):
    try:
        img_r = safe_get(url, timeout=20)
        if img_r and img_r.status_code == 200 and len(img_r.content) > 1000:
            ext = Path(url).suffix.lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                return False
            fname = "{}_{:04d}{}".format(prefix, idx, ext)
            (dest / fname).write_bytes(img_r.content)
            return True
    except Exception:
        pass
    return False


def main():
    # Step 1: Collect all image titles from category + subcategories
    print("Collecting files from Pushkinskaya Street category...")
    cat_title = "Category:Pushkinskaya Street, Rostov-on-Don"
    all_files = get_category_files(cat_title)
    print("  Root category: {} files".format(len(all_files)))

    subcats = get_subcategories(cat_title)
    print("  Subcategories: {}".format(len(subcats)))
    for sc in subcats:
        sub_files = get_category_files(sc["title"])
        all_files.extend(sub_files)
        time.sleep(0.5)

    # Filter to actual images
    image_titles = []
    for f in all_files:
        t = f["title"]
        if any(t.lower().endswith(e) for e in [".jpg", ".jpeg", ".png", ".webp"]):
            image_titles.append(t)

    print("  Total image files: {}".format(len(image_titles)))

    # Step 2: Get URLs for images (sample up to 120)
    random.seed(42)
    random.shuffle(image_titles)
    sample = image_titles[:120]

    print("Fetching URLs...")
    valid = []
    for i, title in enumerate(sample):
        url = get_file_url(title)
        if url:
            valid.append(url)
        if i % 20 == 19:
            print("  {} / {} checked, {} valid".format(i + 1, len(sample), len(valid)))
        time.sleep(0.4)

    print("  Total valid URLs: {}".format(len(valid)))

    # Step 3: Download 3 images per missing landmark
    print("\nDownloading...")
    total = 0
    idx = 0
    for lid in MISSING:
        dest = RAW_DIR / lid
        dest.mkdir(parents=True, exist_ok=True)
        count = 0
        while count < 3 and idx < len(valid):
            url = valid[idx]
            idx += 1
            if download_file(url, dest, lid, count):
                count += 1
            time.sleep(0.5)
        total += count
        print("  {:40s} {}".format(lid, count))

    print("\nTotal downloaded: {}".format(total))
    print("Done!")


if __name__ == "__main__":
    main()
