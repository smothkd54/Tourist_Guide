"""
backend/db.py
-------------
PostgreSQL access layer.

The catalogue (landmarks, photos, model classes) is read once at boot and
kept in memory, so the hot read path is unchanged. Writes — anonymous
reports and shared itineraries — go to PostgreSQL per request.

`DATABASE_URL` is the switch: when it is set the API loads from PostgreSQL;
when it is empty the API falls back to the JSON files in `data/`. The
fallback exists for local development and for the JSON-mode test run; the
composed deployment always sets `DATABASE_URL`.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any

from psycopg import OperationalError
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

# One pool per process. gunicorn prefork gives each worker its own pool, so
# max_size is deliberately small: workers x max_size is the real ceiling.
_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "4"))
_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "1"))

_pool: ConnectionPool | None = None
# After a failed connection, do not make every request wait for the same
# timeout again: GET / probes the database, and a five-second stall per health
# check is worse than reporting the outage immediately. The flag covers both a
# pool that never opened and an open pool whose server went away.
_pool_failed_until = 0.0
_POOL_RETRY_SECONDS = float(os.environ.get("DB_POOL_RETRY_SECONDS", "30"))


class DatabaseUnavailable(RuntimeError):
    """Raised when PostgreSQL is configured but cannot be reached."""


def _check_backoff() -> None:
    now = time.monotonic()
    if now < _pool_failed_until:
        raise DatabaseUnavailable(
            f"database unavailable; retrying in {_pool_failed_until - now:.0f}s"
        )


def _record_failure() -> None:
    global _pool_failed_until
    _pool_failed_until = time.monotonic() + _POOL_RETRY_SECONDS


@contextmanager
def connection():
    """Check out a connection, failing fast while an outage backoff is active.

    Operational errors (server down, pool timeout) arm the backoff; SQL errors
    such as constraint violations pass through untouched.
    """
    _check_backoff()
    try:
        with get_pool().connection() as conn:
            yield conn
    except OperationalError as exc:
        _record_failure()
        raise DatabaseUnavailable(str(exc)) from exc


def dsn() -> str:
    """Return the configured connection string, normalised for libpq."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        # Heroku-style URLs are common; libpq accepts both, but psycopg's
        # parser is happier with the canonical scheme.
        url = "postgresql://" + url[len("postgres://"):]
    return url


def is_configured() -> bool:
    return bool(dsn())


def get_pool() -> ConnectionPool:
    """Open the pool on first use, with a short timeout.

    A hanging pool would hold the whole boot sequence, so a missing database
    fails in seconds and the caller can decide to fall back.
    """
    global _pool
    if _pool is None:
        _check_backoff()
        pool = ConnectionPool(
            dsn(),
            min_size=_POOL_MIN,
            max_size=_POOL_MAX,
            timeout=5,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        try:
            pool.open(wait=True, timeout=10)
        except Exception as exc:  # pragma: no cover - environment dependent
            pool.close()
            _record_failure()
            raise DatabaseUnavailable(str(exc)) from exc
        _pool = pool
    return _pool


def close_pool() -> None:
    """Close the pool (tests and shutdown)."""
    global _pool, _pool_failed_until
    if _pool is not None:
        _pool.close()
        _pool = None
    _pool_failed_until = 0.0


def health() -> dict[str, Any]:
    """Cheap liveness probe used by GET /."""
    started = time.perf_counter()
    try:
        with connection() as conn:
            row = conn.execute("SELECT current_setting('server_version') AS version").fetchone()
        return {
            "status": "ok",
            "version": row["version"] if row else None,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


# ── catalogue (read) ─────────────────────────────────────────────────────────

_LANDMARKS_SQL = """
SELECT
    l.id, l.name, l.name_ru, l.address, l.year_built,
    l.building_type AS type, l.style, l.architect, l.description,
    l.fun_fact, l.lat, l.lon, l.coordinate_source, l.angles,
    p.author, p.license, p.license_url, p.source, p.source_url
FROM landmarks l
LEFT JOIN photos p
       ON p.landmark_id = l.id AND p.is_published
ORDER BY l.sort_order, l.id
"""


def fetch_landmarks() -> list[dict[str, Any]]:
    """Return landmarks shaped exactly like `data/landmarks.json` records.

    The published photo credit is attached as `photo_attribution`, matching
    what the JSON loader and both clients already expect.
    """
    with connection() as conn:
        rows = conn.execute(_LANDMARKS_SQL).fetchall()

    landmarks: list[dict[str, Any]] = []
    for row in rows:
        landmark = {
            "id": row["id"],
            "name": row["name"],
            "name_ru": row["name_ru"],
            "address": row["address"],
            "year_built": row["year_built"],
            "type": row["type"],
            "style": row["style"],
            "architect": row["architect"],
            "description": row["description"],
            "fun_fact": row["fun_fact"],
            "lat": row["lat"],
            "lon": row["lon"],
            "coordinate_source": row["coordinate_source"],
            "angles": list(row["angles"] or []),
        }
        if row["author"]:
            landmark["photo_attribution"] = {
                "author": row["author"],
                "license": row["license"] or "",
                "license_url": row["license_url"] or "",
                "source_url": row["source_url"] or "",
            }
        landmarks.append(landmark)
    return landmarks


def count_stats() -> dict[str, Any]:
    """Counts used by /admin/stats and `scripts/admin.py stats`."""
    sql = """
    SELECT
        (SELECT count(*) FROM landmarks)::int                          AS landmarks,
        (SELECT count(*) FROM photos WHERE is_published)::int          AS published_photos,
        (SELECT count(*) FROM model_classes)::int                      AS classes,
        (SELECT count(*) FROM model_classes WHERE is_validated)::int   AS validated_classes,
        (SELECT count(*) FROM itineraries)::int                        AS itineraries,
        (SELECT count(*) FROM reports)::int                            AS reports,
        (SELECT count(*) FROM reports WHERE status = 'open')::int      AS open_reports,
        (SELECT count(*) FROM reports
          WHERE created_at > now() - interval '7 days')::int           AS reports_last_7_days,
        (SELECT count(*) FROM itineraries
          WHERE created_at > now() - interval '7 days')::int           AS itineraries_last_7_days,
        pg_database_size(current_database())::bigint                   AS database_bytes
    """
    with connection() as conn:
        return conn.execute(sql).fetchone()


# ── reports (write + admin read) ─────────────────────────────────────────────

def create_report(landmark_id: str | None, category: str, message: str) -> dict[str, Any]:
    sql = """
    INSERT INTO reports (landmark_id, category, message)
    VALUES (%s, %s, %s)
    RETURNING id::text AS id, status, created_at
    """
    with connection() as conn:
        row = conn.execute(sql, (landmark_id, category, message)).fetchone()
    row["created_at"] = row["created_at"].isoformat()
    return row


def list_reports(status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    where = ""
    params: list[Any] = []
    if status:
        where = "WHERE r.status = %s"
        params.append(status)
    params.extend([limit, offset])
    sql = f"""
    SELECT r.id::text AS id, r.landmark_id, l.name AS landmark_name,
           r.category, r.message, r.status, r.created_at, r.resolved_at
    FROM reports r
    LEFT JOIN landmarks l ON l.id = r.landmark_id
    {where}
    ORDER BY r.created_at DESC
    LIMIT %s OFFSET %s
    """
    with connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    for row in rows:
        row["created_at"] = row["created_at"].isoformat()
        if row["resolved_at"]:
            row["resolved_at"] = row["resolved_at"].isoformat()
    return rows


def update_report_status(report_id: str, status: str) -> dict[str, Any] | None:
    sql = """
    UPDATE reports
       SET status = %s,
           resolved_at = CASE WHEN %s = 'open' THEN NULL ELSE now() END
     WHERE id = %s
    RETURNING id::text AS id, status, resolved_at
    """
    with connection() as conn:
        row = conn.execute(sql, (status, status, report_id)).fetchone()
    if row is None:
        return None
    if row["resolved_at"]:
        row["resolved_at"] = row["resolved_at"].isoformat()
    return row


# ── itineraries (write + read) ───────────────────────────────────────────────

def create_itinerary(
    start_landmark_id: str,
    mode: str,
    route: dict[str, Any],
    minutes: int | None = None,
) -> str:
    """Persist a planned route and its stops; return the new UUID."""
    stops = route.get("stops", [])
    total_minutes = route.get("total_minutes")
    sql = """
    INSERT INTO itineraries (start_landmark_id, minutes, mode, total_minutes, route)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id::text AS id
    """
    with connection() as conn:
        row = conn.execute(
            sql,
            (
                start_landmark_id,
                minutes,
                mode,
                int(round(total_minutes)) if total_minutes is not None else None,
                Jsonb(route),
            ),
        ).fetchone()
        itinerary_id = row["id"]

        for position, stop in enumerate(stops):
            conn.execute(
                """
                INSERT INTO itinerary_items
                    (itinerary_id, position, landmark_id, dwell_minutes)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    itinerary_id,
                    position,
                    stop["id"],
                    stop.get("estimated_visit_minutes"),
                ),
            )
    return itinerary_id


def get_itinerary(itinerary_id: str) -> dict[str, Any] | None:
    sql = """
    SELECT id::text AS id, start_landmark_id, mode, minutes,
           total_minutes, route, created_at
    FROM itineraries
    WHERE id = %s
    """
    with connection() as conn:
        row = conn.execute(sql, (itinerary_id,)).fetchone()
    if row is None:
        return None
    row["created_at"] = row["created_at"].isoformat()
    return row
