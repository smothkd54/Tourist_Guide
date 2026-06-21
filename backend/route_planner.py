"""
backend/route_planner.py
--------------------------
OSRM-backed walking route planning, used by the /plan endpoint in app.py.

Free, no API key. Uses the public OSRM demo server (router.project-osrm.org),
which is rate-limited and intended for light use/evaluation — appropriate for
a tourist app prototype, not high-traffic production.
"""

import requests
from typing import List, Dict, Any, Optional

OSRM_BASE = "https://router.project-osrm.org"
VISIT_MINUTES_DEFAULT = 8

# Per-type visit-time estimates, derived from landmark["type"] (already
# present on every entry in landmarks.json — no extra data collection
# needed). These are reasonable defaults, not measured data; there is no
# free API that reports actual tourist dwell time per site. A landmark's
# own "visit_minutes" field, if present, always takes priority over this
# table — this is a fallback for entries that don't specify one.
VISIT_MINUTES_BY_TYPE = {
    # quick glance / walk-by — under a minute to take in
    "monument":                4,
    "monument / bust":         4,
    "street art":              3,
    "sculpture":               3,
    "fountain":                4,
    "urban heritage feature":  2,
    "urban green heritage":    5,
    "park gate":               3,
    "memorial":                5,
    "public art":              4,

    # walk around / read a plaque / take photos from multiple angles
    "historic residence":      5,
    "merchant mansion":        6,
    "revenue house":           5,
    "apartment house":         5,
    "apartment building":      5,

    # go inside, browse, sit down — meaningfully longer
    "mansion / museum":       30,
    "institutional building": 10,
    "mansion / university library": 10,
    "university library / mansion": 10,
    "university building":     8,
    "educational building":    8,
    "religious building":     12,
    "cathedral":               15,
    "theater":                 10,
    "cinema":                  10,
}


def estimate_visit_minutes(landmark: Dict, fallback: int = VISIT_MINUTES_DEFAULT) -> int:
    """
    Per-stop visit time, in priority order:
      1. landmark["visit_minutes"] if explicitly set in landmarks.json
      2. VISIT_MINUTES_BY_TYPE lookup keyed on landmark["type"] (lowercased)
      3. the fallback default (the old flat constant, or a user override)
    """
    if landmark.get("visit_minutes") is not None:
        return landmark["visit_minutes"]

    type_key = landmark.get("type", "").strip().lower()
    if type_key in VISIT_MINUTES_BY_TYPE:
        return VISIT_MINUTES_BY_TYPE[type_key]

    return fallback


def osrm_table(landmarks: List[Dict]) -> Dict:
    """Get a real walking duration/distance matrix for all landmarks via OSRM /table."""
    coords = ";".join(f"{lm['lon']},{lm['lat']}" for lm in landmarks)
    url = f"{OSRM_BASE}/table/v1/foot/{coords}"
    r = requests.get(url, params={"annotations": "duration,distance"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table failed: {data.get('message')}")
    return {"durations": data["durations"], "distances": data["distances"]}


def osrm_route_geometry(coords_seq: List[tuple]) -> Optional[Dict]:
    """Get full walking route geometry (GeoJSON) for the final ordered stop sequence."""
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


def plan_custom_route(
    landmarks: List[Dict],
    start_id: str,
    optimize_order: bool = True
) -> Dict[str, Any]:
    """
    Plan a walking route for user-selected landmarks.

    landmarks: List of user-selected landmark dicts (must have lat/lon)
    start_id: ID of the starting landmark
    optimize_order: If True, reorder landmarks for shortest walking distance.
                    If False, keep user's original order.

    Returns the same format as plan_route().
    """
    if len(landmarks) < 1:
        raise ValueError("Need at least 1 landmark.")

    if len(landmarks) == 1:
        lm = landmarks[0]
        return {
            "stops": [{
                "id": lm["id"],
                "name": lm["name"],
                "lat": lm["lat"],
                "lon": lm["lon"],
                "estimated_visit_minutes": estimate_visit_minutes(lm),
            }],
            "total_walking_minutes": 0,
            "total_visit_minutes": estimate_visit_minutes(lm),
            "total_minutes": estimate_visit_minutes(lm),
            "route_geometry": None,
        }

    matrix = osrm_table(landmarks)
    durations = matrix["durations"]

    id_to_idx = {lm["id"]: i for i, lm in enumerate(landmarks)}
    if start_id not in id_to_idx:
        raise ValueError(f"Start landmark '{start_id}' not found in provided list.")
    start_idx = id_to_idx[start_id]

    if optimize_order:
        visited = [start_idx]
        remaining = set(range(len(landmarks))) - {start_idx}

        while remaining:
            current = visited[-1]
            candidates = sorted(
                remaining,
                key=lambda j: durations[current][j] if durations[current][j] is not None else float('inf')
            )
            if not candidates:
                break
            nxt = candidates[0]
            if durations[current][nxt] is None:
                remaining.discard(nxt)
                continue
            visited.append(nxt)
            remaining.discard(nxt)

        ordered = [landmarks[i] for i in visited]
    else:
        start_lm = next(lm for lm in landmarks if lm["id"] == start_id)
        others = [lm for lm in landmarks if lm["id"] != start_id]
        ordered = [start_lm] + others

    total_walk_secs = 0
    for i in range(1, len(ordered)):
        prev_id, cur_id = ordered[i - 1]["id"], ordered[i]["id"]
        prev_idx, cur_idx = id_to_idx[prev_id], id_to_idx[cur_id]
        walk = durations[prev_idx][cur_idx]
        if walk is not None:
            total_walk_secs += walk

    total_visit_secs = sum(estimate_visit_minutes(lm) * 60 for lm in ordered)

    coords_seq = [(lm["lat"], lm["lon"]) for lm in ordered]
    geometry = osrm_route_geometry(coords_seq)

    return {
        "stops": [
            {
                "id": lm["id"],
                "name": lm["name"],
                "lat": lm["lat"],
                "lon": lm["lon"],
                "estimated_visit_minutes": estimate_visit_minutes(lm),
            }
            for lm in ordered
        ],
        "total_walking_minutes": round(total_walk_secs / 60, 1),
        "total_visit_minutes": round(total_visit_secs / 60, 1),
        "total_minutes": round((total_walk_secs + total_visit_secs) / 60, 1),
        "route_geometry": geometry,
    }


def plan_route(
    landmarks: List[Dict],
    start_idx: int,
    minutes_budget: int,
    visit_minutes: int = None
) -> Dict[str, Any]:
    """
    Plan a walking route from a start landmark, greedily visiting the nearest
    unvisited landmark each step, until the time budget (walking + visit time
    per stop) is used up. Returns stops, total times, and real path geometry.

    visit_minutes:
      If given, used as a flat override for every stop (old behavior,
      still supported for callers who want a fixed pace). If None
      (the default), each stop's dwell time is estimated from its
      landmark type via estimate_visit_minutes() — a museum gets more
      time budgeted than a street sculpture, instead of every stop
      costing the same fixed amount regardless of what it actually is.
    """
    n = len(landmarks)
    if n < 2:
        raise ValueError("Need at least 2 geocoded landmarks.")

    matrix = osrm_table(landmarks)
    durations = matrix["durations"]

    def visit_secs_for(idx: int) -> int:
        if visit_minutes is not None:
            return visit_minutes * 60
        return estimate_visit_minutes(landmarks[idx]) * 60

    visited = [start_idx]
    remaining = set(range(n)) - {start_idx}
    total_secs = minutes_budget * 60
    time_used = visit_secs_for(start_idx)

    while remaining:
        current = visited[-1]
        candidates = sorted(
            remaining,
            key=lambda j: durations[current][j] if durations[current][j] is not None else float('inf')
        )
        if not candidates:
            break
        nxt = candidates[0]
        travel = durations[current][nxt]
        if travel is None:
            remaining.discard(nxt)
            continue
        projected = time_used + travel + visit_secs_for(nxt)
        if projected > total_secs:
            break
        visited.append(nxt)
        remaining.discard(nxt)
        time_used = projected

    route_landmarks = [landmarks[i] for i in visited]

    total_walk_secs = 0
    for i in range(1, len(visited)):
        prev, cur = visited[i - 1], visited[i]
        total_walk_secs += durations[prev][cur]

    total_visit_secs = sum(visit_secs_for(i) for i in visited)

    coords_seq = [(lm["lat"], lm["lon"]) for lm in route_landmarks]
    geometry = osrm_route_geometry(coords_seq)

    return {
        "stops": [
            {
                "id": lm["id"],
                "name": lm["name"],
                "lat": lm["lat"],
                "lon": lm["lon"],
                "estimated_visit_minutes": (
                    visit_minutes if visit_minutes is not None
                    else estimate_visit_minutes(lm)
                ),
            }
            for lm in route_landmarks
        ],
        "total_walking_minutes": round(total_walk_secs / 60, 1),
        "total_visit_minutes": round(total_visit_secs / 60, 1),
        "total_minutes": round((total_walk_secs + total_visit_secs) / 60, 1),
        "route_geometry": geometry,
    }