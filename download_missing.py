"""
download_missing.py — targeted download for the 15 landmarks with no photos.
Uses broader Russian/English search terms against Wikimedia Commons.
"""
import requests
import time
from pathlib import Path

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "RostovTouristApp/1.0 (educational project)"}
RAW_DIR = Path("data/raw")

searches = {
    "vysotsky_monument": [
        "памятник Высоцкому Ростов-на-Дону",
        "Vysotsky Rostov-on-Don",
    ],
    "pushkin_spheres": [
        "Пушкинский бульвар Ростов-на-Дону",
        "Пушкинская улица Ростов шар",
    ],
    "lyre_fountain": [
        "Пушкинский бульвар фонтан Ростов",
        "Пушкинский фонтан Ростов-на-Дону",
    ],
    "bakulin_house": [
        "Пушкинская улица Ростов-на-Дону дом",
        "доходный дом Пушкинская Ростов",
    ],
    "literary_figures_house": [
        "дом литераторов Ростов-на-Дону",
        "Пушкинская Ростов литераторы",
    ],
    "budyonny_bust": [
        "бюст Будённого Ростов-на-Дону",
        "памятник Будённому Ростов",
    ],
    "lanterns_1904": [
        "Пушкинский бульвар фонари Ростов",
        "освещение Пушкинская Ростов",
    ],
    "vorozhein_house": [
        "Ворожеина дом Ростов-на-Дону",
        "Доходный дом Ворожеина",
    ],
    "green_boulevard": [
        "Пушкинский бульвар аллея Ростов",
        "зелёный бульвар Ростов",
    ],
    "school_49": [
        "школа Пушкинская Ростов-на-Дону",
        "School Rostov-on-Don",
    ],
    "sorge_bust": [
        "Зорге Ростов-на-Дону",
        "Сквер Славы Зорге Ростов",
    ],
    "writers_busts": [
        "писатели Ростов-на-Дону памятник",
        "писательский бульвар Ростов",
    ],
    "grinshteyn_revenue_house": [
        "доходный дом Пушкинская 9 Ростов",
        "Гринштейн Ростов",
    ],
    "sculpture_squirrel": [
        "белка Пушкинский бульвар Ростов",
        "скульптура животных Ростов бульвар",
    ],
    "pushkin_fairytale_sculptures": [
        "сказки Пушкина скульптура Ростов",
        "деревянные скульптуры Пушкинский",
    ],
}


def download_image(title, dest_dir, prefix):
    """Download a single image file from Wikimedia Commons."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|size",
        "format": "json",
    }
    r = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=10)
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        ii = page.get("imageinfo", [{}])[0]
        url = ii.get("url", "")
        if not url:
            continue
        if not any(url.lower().endswith(e) for e in [".jpg", ".jpeg", ".png", ".webp"]):
            continue
        try:
            img_r = requests.get(url, headers=HEADERS, timeout=15)
            if img_r.status_code == 200 and len(img_r.content) > 1000:
                ext = Path(url).suffix.lower()
                count = len(list(dest_dir.glob(prefix + "_*")))
                fname = "{}_{:04d}{}".format(prefix, count, ext)
                (dest_dir / fname).write_bytes(img_r.content)
                return True
        except Exception:
            pass
    return False


def main():
    total = 0
    for lid, terms in searches.items():
        dest = RAW_DIR / lid
        dest.mkdir(parents=True, exist_ok=True)
        existing = len(list(dest.glob("*")))
        if existing >= 2:
            print("  skip {} (already {})".format(lid, existing))
            continue

        count = 0
        for term in terms:
            r = requests.get(
                COMMONS_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": term,
                    "srnamespace": "6",
                    "srlimit": "10",
                    "format": "json",
                },
                headers=HEADERS,
                timeout=10,
            )
            hits = r.json().get("query", {}).get("search", [])
            for h in hits:
                t = h["title"]
                if t.lower().endswith(".pdf") or t.lower().endswith(".djvu"):
                    continue
                if download_image(t, dest, lid):
                    count += 1
                    if count >= 3:
                        break
                time.sleep(0.3)
            if count >= 3:
                break
            time.sleep(0.3)

        total += count
        print("  {:40s} downloaded {}".format(lid, count))

    print("\nTotal new images: {}".format(total))


if __name__ == "__main__":
    main()
