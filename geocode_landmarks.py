"""
geocode_landmarks.py
--------------------
Fetches real GPS coordinates for Pushkinskaya Street landmarks
from OpenStreetMap's Nominatim API (free, no key required).

USAGE
-----
  python geocode_landmarks.py
  python geocode_landmarks.py --force
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

DATA_DIR = Path("data")
LANDMARKS_JSON = DATA_DIR / "landmarks.json"
NOMINATIM_API = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
SLEEP = 1.1


def load_landmarks():
    with open(LANDMARKS_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_landmarks(data):
    with open(LANDMARKS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def geocode(query):
    try:
        r = requests.get(NOMINATIM_API, params={"q": query, "format": "json", "limit": 1}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"]), results[0].get("display_name", "")[:100]
    except Exception as e:
        return None, None, str(e)
    return None, None, "no results"


def main():
    force = "--force" in sys.argv

    data = load_landmarks()
    landmarks = data["landmarks"]

    queries_run = 0
    for lm in landmarks:
        if lm.get("lat") is not None and lm.get("lon") is not None and not force:
            continue

        lid = lm["id"]
        name = lm.get("name", "")
        name_ru = lm.get("name_ru", "")
        address = lm.get("address", "")

        # Try address first, then name+city, then name_ru+city, then fallback
        queries = []
        if address and "Pushkinskaya" in address:
            queries.append(f"{address}, Rostov-on-Don")
        if address and "Пушкинская" in address:
            queries.append(f"{address}, Ростов-на-Дону")
        if name_ru:
            queries.append(f"{name_ru}, Ростов-на-Дону")
        if name:
            queries.append(f"{name}, Rostov-on-Don")
        # Last resort: address number on Pushkinskaya
        nums = re.findall(r'\d+', address)
        if nums:
            queries.append(f"Pushkinskaya {nums[0]}, Rostov-on-Don")
        queries.append("Pushkinskaya Street, Rostov-on-Don")

        for q in queries:
            queries_run += 1
            lat, lon, info = geocode(q)
            if lat is not None:
                lm["lat"] = lat
                lm["lon"] = lon
                lm["coordinate_source"] = "nominatim"
                print(f"  ✓ {lid:<30} ({lat:.5f}, {lon:.5f})")
                break
            if queries_run % 10 == 0:
                time.sleep(SLEEP)

    save_landmarks(data)

    geocoded = sum(1 for lm in landmarks if lm.get("lat") is not None)
    print(f"\nGeocoded: {geocoded}/{len(landmarks)}")


if __name__ == "__main__":
    main()
