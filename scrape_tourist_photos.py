"""
scrape_tourist_photos.py
-------------------------
Scrapes tourist review photos of Pushkinskaya Street landmarks from
public Russian travel review sites (tourister.ru) and Russian Wikipedia.

USAGE
-----
  python scrape_tourist_photos.py
  python scrape_tourist_photos.py --id pushkin_monument
  python scrape_tourist_photos.py --n 30 --delay 2.0

OUTPUT
------
  data/raw/<landmark_id>/    downloaded tourist photos

REQUIREMENTS
------------
  pip install requests pillow beautifulsoup4
"""

import argparse
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
from PIL import Image

DATA_DIR       = Path("data")
RAW_DIR        = DATA_DIR / "raw"
LANDMARKS_JSON = DATA_DIR / "landmarks.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
}
MIN_WIDTH = 400
IMG_EXTS  = {".jpg", ".jpeg", ".png", ".webp"}
TIMEOUT   = 20

SEARCH_TERMS = {
    "pushkin_monument":        ["памятник пушкину ростов-на-дону"],
    "kirov_monument":          ["памятник кирову ростов"],
    "chekhov_monument":        ["памятник чехову ростов-на-дону"],
    "vysotsky_monument":       ["памятник высоцкому ростов"],
    "pushkin_spheres":         ["пушкинские шары ростов бульвар"],
    "lyre_fountain":           ["фонтан лира ростов пушкинская"],
    "library_fountain":        ["фонтан библиотека пушкинская ростов"],
    "don_state_library":       ["донская государственная библиотека ростов"],
    "museum_fine_arts":        ["музей изобразительных искусств ростов пушкинская"],
    "paramonov_mansion_sfeu":  ["особняк парамонова ростов пушкинская 148"],
    "kramer_mansion":          ["особняк крамера ростов пушкинская 114"],
    "kramer_revenue_house":    ["доходный дом крамера ростов пушкинская 116"],
    "spielrein_mansion":       ["особняк шпильрейн ростов пушкинская 83"],
    "zvorykin_house":          ["дом зворыкина ростов пушкинская"],
    "gavala_house":            ["дом гавала ростов пушкинская 93"],
    "suprunov_mansion":        ["особняк супрунова ростов пушкинская 79"],
    "lashch_revenue_house":    ["дом ливус ростов пушкинская 75"],
    "mnatsakanova_house":      ["дом мнацакановой ростов пушкинская 65"],
    "kushnarev_house":         ["дом кушнарева ростов пушкинская 51"],
    "reznichenko_house":       ["дом резниченко ростов пушкинская 47"],
    "bakulin_house":           ["дом бакулина ростов пушкинская 13"],
    "bostrikiny_house":        ["дом бострикиных ростов пушкинская 106"],
    "literary_figures_house":  ["пушкинская 78 ростов"],
    "annunciation_church":     ["греческая церковь благовещения ростов"],
    "rostov_medical_university":["медуниверситет ростов пушкинская"],
    "sfeu_library":            ["библиотека ЮФУ ростов пушкинская"],
    "memorial_nazi_victims":   ["мемориал жертвам оккупации ростов 1943"],
    "budyonny_bust":           ["бюст буденного ростов пушкинская"],
    "sholokhov_monument":      ["памятник шолохову ростов"],
    "lanterns_1904":           ["фонари пушкинская ростов ночь"],
    "gorky_park_gate":         ["парк горького ростов ворота"],
    "cathedral_nativity":      ["собор рождества богородицы ростов"],
    "gorky_theater":           ["театр горького ростов"],
    "gorky_theater_fountain":  ["фонтан театральная площадь ростов"],
    "underground_mosaics":     ["мозаики переходов ростов"],
    "musical_theater":         ["музыкальный театр ростов рояль"],
    "vorozhein_house":         ["пушкинская улица ростов старинные дома"],
    "green_boulevard":         ["пушкинская бульвар ростов аллея"],
    "school_49":               ["школа 49 ростов пушкинская"],
}

WIKI_RU_ARTICLES = {
    "pushkin_monument":        "Памятник А. С. Пушкину (Ростов-на-Дону)",
    "kirov_monument":          "Памятник С. М. Кирову (Ростов-на-Дону)",
    "chekhov_monument":        "Памятник А. П. Чехову (Ростов-на-Дону)",
    "don_state_library":       "Донская государственная публичная библиотека",
    "museum_fine_arts":        "Ростовский областной музей изобразительных искусств",
    "paramonov_mansion_sfeu":  "Особняк Парамонова (Ростов-на-Дону)",
    "spielrein_mansion":       "Дом Шпильрейн",
    "zvorykin_house":          "Дом Зворыкина (Ростов-на-Дону)",
    "annunciation_church":     "Церковь Благовещения Пресвятой Богородицы (Ростов-на-Дону)",
    "cathedral_nativity":      "Собор Рождества Пресвятой Богородицы (Ростов-на-Дону)",
    "gorky_theater":           "Ростовский академический театр драмы имени Максима Горького",
    "musical_theater":         "Ростовский музыкальный театр",
    "gorky_park_gate":         "Парк Горького (Ростов-на-Дону)",
    "sholokhov_monument":      "Памятник М. А. Шолохову (Ростов-на-Дону)",
}


def load_landmarks():
    with open(LANDMARKS_JSON) as f:
        return json.load(f)["landmarks"]


def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()[:10]


def download_one(url, dest):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if img.width < MIN_WIDTH:
            return False
        img.save(dest, "JPEG", quality=90)
        return True
    except Exception:
        return False


def extract_img_urls(soup, base_url):
    found = set()
    for img in soup.find_all("img"):
        for attr in ["src", "data-src", "data-original"]:
            val = img.get(attr, "")
            if val and any(val.lower().endswith(e) for e in IMG_EXTS):
                url = urljoin(base_url, val)
                if not any(x in url.lower() for x in
                           ["thumb", "avatar", "icon", "logo", "50x50", "100x100"]):
                    found.add(url)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(href.lower().endswith(e) for e in IMG_EXTS):
            found.add(urljoin(base_url, href))
    return list(found)


def fetch_soup(url, delay):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        time.sleep(delay)
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"      [error: {e}]")
        return None


def wikipedia_image_urls(article_title, delay):
    """Get image URLs from a Russian Wikipedia article."""
    urls = []
    # Step 1: get image file titles from the article
    params = {
        "action": "query", "titles": article_title,
        "prop": "images", "imlimit": 20, "format": "json",
    }
    try:
        r = requests.get("https://ru.wikipedia.org/w/api.php",
                         params=params, headers=HEADERS, timeout=15)
        data = r.json()
        time.sleep(delay)
        pages = data.get("query", {}).get("pages", {})
        titles = []
        for pg in pages.values():
            for img in pg.get("images", []):
                t = img.get("title", "")
                if any(t.lower().endswith(e) for e in [".jpg", ".jpeg", ".png"]):
                    titles.append(t)

        # Step 2: resolve each title to a direct URL via Commons API
        for t in titles[:12]:
            ip = {
                "action": "query", "titles": t,
                "prop": "imageinfo", "iiprop": "url|size", "format": "json",
            }
            ir = requests.get("https://commons.wikimedia.org/w/api.php",
                              params=ip, headers=HEADERS, timeout=15)
            idata = ir.json()
            for pg in idata.get("query", {}).get("pages", {}).values():
                ii = pg.get("imageinfo", [])
                if ii and ii[0].get("width", 0) >= MIN_WIDTH:
                    urls.append(ii[0]["url"])
            time.sleep(0.4)
    except Exception as e:
        print(f"      [Wikipedia error: {e}]")
    return urls


def tourister_search(query, delay):
    url = f"https://tourister.ru/search?query={quote(query)}&type=photo"
    soup = fetch_soup(url, delay)
    if not soup:
        return []
    return extract_img_urls(soup, url)


def process_landmark(lm, n, delay, dry_run):
    lid  = lm["id"]
    dest = RAW_DIR / lid
    dest.mkdir(parents=True, exist_ok=True)

    existing = len(list(dest.glob("*.jpg")))
    needed   = max(0, n - existing)
    if needed == 0:
        print(f"    ✅ {existing}/{n} already present — skipping")
        return existing

    print(f"    Need {needed} more (have {existing})")

    all_urls = []
    seen     = set()

    # tier 1: Russian Wikipedia
    if lid in WIKI_RU_ARTICLES:
        art = WIKI_RU_ARTICLES[lid]
        print(f"    🌐 ru.wikipedia: {art[:55]}", end=" ", flush=True)
        wu = wikipedia_image_urls(art, delay)
        print(f"→ {len(wu)}")
        all_urls.extend(wu)

    # tier 2: tourister.ru
    for term in SEARCH_TERMS.get(lid, [])[:2]:
        if len(all_urls) >= needed * 2:
            break
        print(f"    🔍 tourister: {term[:50]}", end=" ", flush=True)
        tu = tourister_search(term, delay)
        print(f"→ {len(tu)}")
        all_urls.extend(tu)

    # deduplicate
    unique = []
    for u in all_urls:
        h = url_hash(u)
        if h not in seen:
            seen.add(h)
            unique.append(u)

    print(f"    → {len(unique)} unique candidates found")

    saved = existing
    for url in unique:
        if saved >= n:
            break
        fname = f"{lid}_{saved:04d}_{url_hash(url)}.jpg"
        fpath = dest / fname
        if fpath.exists():
            saved += 1
            continue
        if dry_run:
            print(f"      [DRY RUN] {url[:80]}")
            saved += 1
            continue
        if download_one(url, fpath):
            print(f"      ✓ {fname}")
            saved += 1
        time.sleep(delay * 0.3)

    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n",       type=int,   default=15)
    parser.add_argument("--id",      type=str,   default=None)
    parser.add_argument("--delay",   type=float, default=1.5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    landmarks = load_landmarks()
    if args.id:
        landmarks = [lm for lm in landmarks if lm["id"] == args.id]
        if not landmarks:
            print(f"❌ Unknown id: {args.id}")
            sys.exit(1)

    print(f"\n📸 Pushkinskaya Street Photo Scraper")
    print(f"   {len(landmarks)} landmarks  |  target {args.n} each  |  delay {args.delay}s")
    if args.dry_run:
        print("   MODE: DRY RUN")
    print()

    totals = {}
    for lm in landmarks:
        print(f"\n  ── {lm['name']}")
        totals[lm["id"]] = process_landmark(lm, args.n, args.delay, args.dry_run)

    grand = sum(totals.values())
    print(f"\n{'─'*55}")
    print(f"  Total images: {grand}  |  avg {grand // max(len(landmarks),1)} per landmark")
    print(f"\n  Next:  python collect_data.py  →  python train.py\n")


if __name__ == "__main__":
    main()
