"""
PostgreSQL tests: schema guarantees, reports, admin endpoints, itineraries.

Skipped when DATABASE_URL is not set. CI runs the whole suite twice, once in
JSON mode and once against a seeded PostgreSQL, so these tests are exercised
on every pipeline.
"""

import os
import uuid

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

import backend.app as app_module
from backend import db
from backend.app import app


def _test_database_ready() -> bool:
    """Only touch databases whose name ends in `_test`.

    The fixture truncates reports/itineraries, so pointing the suite at the
    development database would destroy real content. `ALLOW_DB_TESTS=1` is
    the explicit opt-out for a throwaway database with another name.
    """
    if not db.is_configured():
        return False
    name = conninfo_to_dict(db.dsn()).get("dbname", "")
    return name.endswith("_test") or os.environ.get("ALLOW_DB_TESTS") == "1"


pytestmark = pytest.mark.skipif(
    not _test_database_ready(),
    reason="PostgreSQL test database not configured (expected a *_test database)",
)


@pytest.fixture
def client_pg():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clean_writes():
    """Keep write tests independent without recreating the database."""
    with db.get_pool().connection() as conn:
        conn.execute("TRUNCATE reports, itinerary_items, itineraries")
    app_module._report_limiter._requests.clear()
    yield


def _expect_integrity_error(conn, sql, params=()):
    with pytest.raises(psycopg.errors.IntegrityError):
        # A nested transaction is a savepoint: the outer transaction survives
        # the deliberate violation and can keep asserting.
        with conn.transaction():
            conn.execute(sql, params)


def test_seed_counts():
    with db.get_pool().connection() as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT count(*) FROM landmarks) AS landmarks,
                (SELECT count(*) FROM model_classes) AS classes,
                (SELECT count(*) FROM photos WHERE is_published) AS photos
            """
        ).fetchone()
    assert row["landmarks"] == 46
    assert row["classes"] == 29
    assert row["photos"] == 38


def test_landmark_constraints():
    with db.get_pool().connection() as conn:
        _expect_integrity_error(conn, "UPDATE landmarks SET lat = 100 WHERE id = 'pushkin_monument'")
        _expect_integrity_error(conn, "UPDATE landmarks SET lon = -200 WHERE id = 'pushkin_monument'")
        _expect_integrity_error(conn, "UPDATE landmarks SET year_built = 900 WHERE id = 'pushkin_monument'")


def test_published_photo_requires_credit():
    with db.get_pool().connection() as conn:
        _expect_integrity_error(
            conn,
            """
            INSERT INTO photos (id, landmark_id, stored_path, author, license, license_url)
            VALUES ('bad_photo', 'pushkin_monument', 'data/photos/x.jpg', 'Someone', NULL, NULL)
            """,
        )


def test_model_class_index_is_unique():
    with db.get_pool().connection() as conn:
        _expect_integrity_error(
            conn,
            """
            INSERT INTO model_classes (class_name, landmark_id, class_index)
            VALUES ('duplicate_index', 'pushkin_monument', 0)
            """,
        )


def test_report_message_length_is_enforced():
    with db.get_pool().connection() as conn:
        _expect_integrity_error(
            conn,
            "INSERT INTO reports (category, message) VALUES ('other', 'short')",
        )


def test_create_and_resolve_report(client_pg, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")

    created = client_pg.post(
        "/reports",
        json={
            "landmark_id": "pushkin_monument",
            "category": "wrong_photo",
            "message": "This photo shows a different building entirely.",
        },
    )
    assert created.status_code == 201
    report_id = created.get_json()["id"]
    assert created.get_json()["status"] == "open"

    listed = client_pg.get("/admin/reports", headers={"X-Admin-Token": "test-token"})
    assert listed.status_code == 200
    rows = listed.get_json()
    assert [row["id"] for row in rows] == [report_id]
    assert rows[0]["landmark_name"]

    resolved = client_pg.patch(
        f"/admin/reports/{report_id}",
        json={"status": "resolved"},
        headers={"X-Admin-Token": "test-token"},
    )
    assert resolved.status_code == 200
    assert resolved.get_json()["status"] == "resolved"


def test_report_validation(client_pg):
    base = {"category": "other", "message": "A perfectly valid report text."}

    bad_category = client_pg.post("/reports", json={**base, "category": "spam"})
    assert bad_category.status_code == 400

    short = client_pg.post("/reports", json={**base, "message": "short"})
    assert short.status_code == 400

    unknown = client_pg.post("/reports", json={**base, "landmark_id": "not_a_landmark"})
    assert unknown.status_code == 400


def test_admin_requires_token(client_pg, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    denied = client_pg.get("/admin/stats")
    assert denied.status_code == 401

    wrong = client_pg.get("/admin/stats", headers={"X-Admin-Token": "nope"})
    assert wrong.status_code == 401

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    disabled = client_pg.get("/admin/stats", headers={"X-Admin-Token": "test-token"})
    assert disabled.status_code == 503


def test_admin_stats(client_pg, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    response = client_pg.get("/admin/stats", headers={"X-Admin-Token": "test-token"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["landmarks"] == 46
    assert body["published_photos"] == 38
    assert body["data_source"] == "postgres"


def test_itinerary_roundtrip(client_pg, monkeypatch):
    route = {
        "stops": [
            {
                "id": "pushkin_monument",
                "name": "Monument to Alexander Pushkin",
                "lat": 47.22601,
                "lon": 39.719028,
                "estimated_visit_minutes": 15,
            }
        ],
        "total_walking_minutes": 0,
        "total_visit_minutes": 15,
        "total_minutes": 15,
        "route_geometry": None,
    }
    monkeypatch.setattr(app_module, "plan_custom_route", lambda *a, **k: route)

    created = client_pg.post(
        "/itineraries",
        json={"landmarks": ["pushkin_monument"], "start": "pushkin_monument"},
    )
    assert created.status_code == 201
    itinerary_id = created.get_json()["id"]

    fetched = client_pg.get(f"/itineraries/{itinerary_id}")
    assert fetched.status_code == 200
    body = fetched.get_json()
    assert body["id"] == itinerary_id
    assert body["route"]["stops"][0]["id"] == "pushkin_monument"

    assert client_pg.get(f"/itineraries/{uuid.uuid4()}").status_code == 404
    assert client_pg.get("/itineraries/not-a-uuid").status_code == 400


@pytest.mark.skipif(app.data_source == "postgres", reason="JSON-mode behaviour")
def test_writes_unavailable_without_database(client_pg):
    response = client_pg.post(
        "/reports",
        json={"category": "other", "message": "A perfectly valid report text."},
    )
    assert response.status_code == 503
