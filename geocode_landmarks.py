"""
geocode_landmarks.py
---------------------
Fetches real GPS coordinates for Pushkinskaya Street landmarks from
OpenStreetMap's Nominatim API (free, no key required).

USAGE
-----
  python geocode_landmarks.py
  python geocode_landmarks.py --force
  python geocode_landmarks.py --verify     # audit existing coords, no API calls
  python geocode_landmarks.py --fix        # re-geocode only the bad/duplicate entries

WHY --verify AND --fix EXIST
-----------------------------
A previous version of this script had a bug: it always appended a
generic "Pushkinskaya Street, Rostov-on-Don" query as the last
fallback, with no flag indicating that fallback was used. When
Nominatim failed to resolve a more specific query — which happened
for most individual building names, since OSM does not index most of
them — the script silently accepted the street's center point and
labeled it "coordinate_source": "nominatim", identical to a genuine
match. The result was that two thirds of the dataset pointed at one
of two near-identical coordinates while looking fully verified.

This version:
  1. Never accepts the generic street-level query as a landmark's
     final answer. If only the fallback resolves, the landmark is
     left unresolved and flagged, not silently coordinate-stamped.
  2. Sleeps 1.1s before every request (Nominatim policy: max 1/sec),
     not every 10th request.
  3. Uses a proper descriptive User-Agent instead of a spoofed
     browser string, per Nominatim's usage policy.
  4. Tags every successful match with which query string worked, so
     you can audit specificity later.
"""

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import requests

DATA_DIR        = Path("data")
LANDMARKS_JSON  = DATA_DIR / "landmarks.json"
REPORT_JSON     = DATA_DIR / "geocode_report.json"

NOMINATIM_API = "https://nominatim.openstreetmap.org/search"
HEADERS = {
    "User-Agent": (
        "PushkinskayaLandmarkApp/1.0 "
        "(educational project; contact via repository issues)"
    )
}
SLEEP_BETWEEN_REQUESTS = 1.1   # Nominatim policy: max 1 request/second

# The generic fallback query. If a landmark only resolves via this
# query, it is NOT considered geocoded — it's too imprecise to be
# useful (it just means "somewhere on Pushkinskaya Street").
GENERIC_FALLBACK_QUERY = "Pushkinskaya Street, Rostov-on-Don"


def load_landmarks():
    with open(LANDMARKS_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_landmarks(data):
    with open(LANDMARKS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def geocode(query: str):
    """Single Nominatim lookup. Returns (lat, lon, display_name) or (None, None, reason)."""
    try:
        r = requests.get(
            NOMINATIM_API,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "ru"},
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        results = r.json()
        if results:
            top = results[0]
            return float(top["lat"]), float(top["lon"]), top.get("display_name", "")[:120]
        return None, None, "no results"
    except Exception as e:
        return None, None, f"error: {e}"


def build_queries(lm: dict) -> list:
    """
    Ordered list of queries to try, most specific first.
    Deliberately does NOT include the generic street-only query —
    that is handled separately as a non-accepted last resort.
    """
    name     = lm.get("name", "")
    name_ru  = lm.get("name_ru", "")
    address  = lm.get("address", "")
    queries  = []

    if address and "Pushkinskaya" in address:
        queries.append(f"{address}, Rostov-on-Don")
    if address and "Пушкинская" in address:
        queries.append(f"{address}, Ростов-на-Дону")
    if name_ru:
        queries.append(f"{name_ru}, Ростов-на-Дону")
    if name:
        queries.append(f"{name}, Rostov-on-Don")

    nums = re.findall(r"\d+", address)
    if nums:
        queries.append(f"Pushkinskaya {nums[0]}, Rostov-on-Don")

    return queries


def geocode_landmark(lm: dict) -> dict:
    """
    Try each specific query in order. Returns a result dict.
    Never falls through to the generic street query as an accepted answer.
    """
    queries = build_queries(lm)

    for q in queries:
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        lat, lon, info = geocode(q)
        if lat is not None:
            return {
                "status": "found",
                "lat": lat, "lon": lon,
                "matched_query": q,
                "display_name": info,
            }

    # nothing specific resolved — check the generic fallback ONLY to
    # report it, never to accept it as the landmark's coordinate
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    lat, lon, info = geocode(GENERIC_FALLBACK_QUERY)
    if lat is not None:
        return {
            "status": "only_generic_fallback",
            "lat": None, "lon": None,
            "fallback_lat": lat, "fallback_lon": lon,
            "note": "Only the generic street query resolved. Not accepted as a "
                    "landmark-specific coordinate. Add lat/lon manually if you can "
                    "confirm the location, e.g. via openstreetmap.org.",
        }

    return {"status": "not_found", "lat": None, "lon": None}


def cmd_verify(data):
    """Audit current coordinates: flag duplicates without making any API calls."""
    landmarks = data["landmarks"]
    coord_counts = Counter(
        (lm["lat"], lm["lon"]) for lm in landmarks
        if lm.get("lat") is not None
    )
    duplicated_coords = {c for c, n in coord_counts.items() if n > 1}

    print(f"\n{'ID':<30} {'Lat':>12} {'Lon':>12}  Status")
    print("-" * 70)
    flagged = 0
    for lm in landmarks:
        lat, lon = lm.get("lat"), lm.get("lon")
        if lat is None:
            status = "missing"
        elif (lat, lon) in duplicated_coords:
            status = f"DUPLICATE (shared by {coord_counts[(lat, lon)]} landmarks)"
            flagged += 1
        else:
            status = "ok"
        print(f"  {lm['id']:<28} {str(lat):>12} {str(lon):>12}  {status}")

    print(f"\n{len(landmarks)} total landmarks")
    print(f"{flagged} flagged as sharing a duplicate coordinate")
    print(f"{len(duplicated_coords)} distinct duplicate coordinate value(s)")
    if flagged:
        print(f"\nRun: python geocode_landmarks.py --fix")
        print(f"to re-geocode only the flagged entries with stricter matching.\n")


def cmd_geocode(data, force: bool, fix_only: bool):
    landmarks = data["landmarks"]

    if fix_only:
        coord_counts = Counter(
            (lm["lat"], lm["lon"]) for lm in landmarks if lm.get("lat") is not None
        )
        duplicated_coords = {c for c, n in coord_counts.items() if n > 1}
        targets = [
            lm for lm in landmarks
            if lm.get("lat") is None or (lm["lat"], lm["lon"]) in duplicated_coords
        ]
    elif force:
        targets = landmarks
    else:
        targets = [lm for lm in landmarks if lm.get("lat") is None]

    if not targets:
        print("\nNothing to geocode. All landmarks already have coordinates.")
        print("Run with --verify to audit for duplicates, or --force to re-check everything.\n")
        return

    print(f"\nGeocoding {len(targets)} landmark(s)")
    print(f"(rate-limited to 1 request/second per Nominatim usage policy — this will take a while)\n")

    report = {}
    for lm in targets:
        print(f"  {lm['name']}", end=" ")
        result = geocode_landmark(lm)
        report[lm["id"]] = result

        if result["status"] == "found":
            lm["lat"] = result["lat"]
            lm["lon"] = result["lon"]
            lm["coordinate_source"] = f"nominatim ({result['matched_query']})"
            print(f"-> OK  ({result['lat']:.5f}, {result['lon']:.5f})  via \"{result['matched_query']}\"")
        elif result["status"] == "only_generic_fallback":
            lm["lat"] = None
            lm["lon"] = None
            lm["coordinate_source"] = "unresolved — only generic street match, needs manual coordinates"
            print(f"-> UNRESOLVED  (street center only: "
                  f"{result['fallback_lat']:.5f}, {result['fallback_lon']:.5f} — NOT saved)")
        else:
            lm["lat"] = None
            lm["lon"] = None
            lm["coordinate_source"] = "not found"
            print("-> NOT FOUND")

    save_landmarks(data)
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    found      = sum(1 for r in report.values() if r["status"] == "found")
    unresolved = sum(1 for r in report.values() if r["status"] == "only_generic_fallback")
    not_found  = sum(1 for r in report.values() if r["status"] == "not_found")

    print(f"\n{'-'*50}")
    print(f"  Geocoded with specific match : {found}")
    print(f"  Unresolved (street-only)     : {unresolved}")
    print(f"  Not found at all             : {not_found}")
    print(f"{'-'*50}")
    print(f"\nUpdated: {LANDMARKS_JSON}")
    print(f"Report : {REPORT_JSON}")

    if unresolved or not_found:
        print(f"\n{unresolved + not_found} landmark(s) still need coordinates.")
        print("These are buildings OSM does not index individually. Options:")
        print("  1. Look up the address manually at https://www.openstreetmap.org")
        print("     and add \"lat\"/\"lon\" to that entry in landmarks.json by hand.")
        print("  2. Use the building's house-number address point instead of its")
        print("     name (often resolves where the building name does not).")
        print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force",  action="store_true",
                        help="Re-geocode every landmark, even ones that already have coordinates")
    parser.add_argument("--fix",    action="store_true",
                        help="Re-geocode only landmarks with missing or duplicate coordinates")
    parser.add_argument("--verify", action="store_true",
                        help="Audit current coordinates for duplicates, no API calls")
    args = parser.parse_args()

    data = load_landmarks()

    if args.verify:
        cmd_verify(data)
        return

    cmd_geocode(data, force=args.force, fix_only=args.fix)


if __name__ == "__main__":
    main()
