"""
plan_route.py
-------------
Builds a real walking route between landmarks using OSRM, the free
Open Source Routing Machine public demo server. No API key, no cost.

USAGE
-----
  python plan_route.py --minutes 60
  python plan_route.py --minutes 90 --start pushkin_monument
  python plan_route.py --distance-matrix

OUTPUT
------
  data/planned_route.json  — consumed by GET /route in backend/app.py
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

DATA_DIR = Path("data")
LANDMARKS_JSON = DATA_DIR / "landmarks.json"
ROUTE_OUTPUT = DATA_DIR / "planned_route.json"
OSRM_BASE = "https://router.project-osrm.org"
VISIT_MINUTES_DEFAULT = 8


def load_landmarks_with_coords():
    with open(LANDMARKS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return [lm for lm in data["landmarks"] if lm.get("lat") is not None]


def osrm_table(landmarks):
    coords = ";".join(f"{lm['lon']},{lm['lat']}" for lm in landmarks)
    url = f"{OSRM_BASE}/table/v1/foot/{coords}"
    r = requests.get(url, params={"annotations": "duration,distance"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table failed: {data.get('message')}")
    return {"durations": data["durations"], "distances": data["distances"]}


def osrm_route_geometry(coords_seq):
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords_seq)
    url = f"{OSRM_BASE}/route/v1/foot/{coord_str}"
    try:
        r = requests.get(url, params={"geometries": "geojson", "overview": "full"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("code") == "Ok" and data.get("routes"):
            return data["routes"][0]["geometry"]
    except Exception:
        pass
    return None


def plan_walk(landmarks, matrix, start_idx, minutes_budget, visit_minutes):
    n = len(landmarks)
    visited = [start_idx]
    remaining = set(range(n)) - {start_idx}
    total_secs = minutes_budget * 60
    time_used = visit_minutes * 60
    durations = matrix["durations"]

    while remaining:
        current = visited[-1]
        candidates = sorted(remaining, key=lambda j: durations[current][j] if durations[current][j] is not None else 1e9)
        nxt = candidates[0]
        travel = durations[current][nxt]
        if travel is None:
            remaining.discard(nxt)
            continue
        projected = time_used + travel + visit_minutes * 60
        if projected > total_secs:
            break
        visited.append(nxt)
        remaining.discard(nxt)
        time_used = projected
    return visited


def main():
    parser = argparse.ArgumentParser(description="Plan a walking route on Pushkinskaya Street.")
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--visit-minutes", type=int, default=VISIT_MINUTES_DEFAULT)
    parser.add_argument("--distance-matrix", action="store_true")
    args = parser.parse_args()

    landmarks = load_landmarks_with_coords()

    if len(landmarks) < 2:
        print("Need at least 2 geocoded landmarks. Run geocode_landmarks.py first.")
        sys.exit(1)

    print(f"{len(landmarks)} landmarks with coordinates.")

    if args.distance_matrix:
        matrix = osrm_table(landmarks)
        print(f"{'':20}" + "".join(f"{lm['id'][:10]:>12}" for lm in landmarks))
        for i, lm in enumerate(landmarks):
            row = "".join(f"{matrix['durations'][i][j]/60:>11.1f}m" if matrix['durations'][i][j] else f"{'--':>12}" for j in range(len(landmarks)))
            print(f"{lm['id'][:18]:<20}{row}")
        return

    start_idx = 0
    if args.start:
        ids = [lm["id"] for lm in landmarks]
        if args.start not in ids:
            print(f"Landmark '{args.start}' not found. Available: {', '.join(ids[:10])}...")
            sys.exit(1)
        start_idx = ids.index(args.start)

    print("Fetching walking matrix from OSRM...")
    matrix = osrm_table(landmarks)

    print(f"Planning {args.minutes}-minute walk from {landmarks[start_idx]['name']}...")
    route_indices = plan_walk(landmarks, matrix, start_idx, args.minutes, args.visit_minutes)
    route = [landmarks[i] for i in route_indices]

    print(f"{'Stop':<5} {'Landmark':<35} {'Walk from prev':>16}")
    print("-" * 60)
    total_walk_secs = 0
    for i, lm in enumerate(route):
        if i == 0:
            print(f"{i+1:<5} {lm['name'][:33]:<35} {'(start)':>16}")
        else:
            prev = route_indices[i-1]
            cur = route_indices[i]
            secs = matrix["durations"][prev][cur]
            total_walk_secs += secs
            print(f"{i+1:<5} {lm['name'][:33]:<35} {secs/60:>14.1f} min")

    total_visit = len(route) * args.visit_minutes
    total = total_walk_secs / 60 + total_visit
    print("-" * 60)
    print(f"  Stops: {len(route)}, Walking: {total_walk_secs/60:.1f}min, Total: {total:.1f}min")

    print("Fetching path geometry...")
    coords_seq = [(lm["lat"], lm["lon"]) for lm in route]
    geometry = osrm_route_geometry(coords_seq)

    output = {
        "start": landmarks[start_idx]["id"],
        "minutes_budget": args.minutes,
        "visit_minutes_per_stop": args.visit_minutes,
        "stops": [{"id": lm["id"], "name": lm["name"], "lat": lm["lat"], "lon": lm["lon"]} for lm in route],
        "total_walking_minutes": round(total_walk_secs / 60, 1),
        "total_minutes": round(total, 1),
        "route_geometry": geometry,
    }

    ROUTE_OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Saved: {ROUTE_OUTPUT}")


if __name__ == "__main__":
    main()
