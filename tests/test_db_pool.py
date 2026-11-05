"""Pool failure handling does not need a live database."""

from contextlib import contextmanager

import pytest
from psycopg import OperationalError

from backend import db


class _FailingPool:
    def __init__(self, *args, **kwargs):
        self.created = True

    def open(self, **kwargs):
        raise RuntimeError("connection refused")

    def close(self):
        pass


def test_failed_pool_open_is_not_retried_on_every_request(monkeypatch):
    """GET / probes the database; a down database must not stall every probe.

    After one failed open, get_pool() raises immediately from the backoff
    instead of paying the ten-second pool timeout again.
    """
    attempts = []

    class CountingPool(_FailingPool):
        def __init__(self, *args, **kwargs):
            attempts.append(1)
            super().__init__(*args, **kwargs)

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:1/db")
    monkeypatch.setattr(db, "ConnectionPool", CountingPool)
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(db, "_pool_failed_until", 0.0)
    monkeypatch.setattr(db, "_POOL_RETRY_SECONDS", 30.0)

    with pytest.raises(db.DatabaseUnavailable):
        db.get_pool()
    with pytest.raises(db.DatabaseUnavailable):
        db.get_pool()

    assert len(attempts) == 1


def test_open_pool_that_loses_the_server_backs_off(monkeypatch):
    """The server can go away after boot; health checks must still fail fast.

    Without the shared backoff every GET / waits five seconds for a pool
    checkout, which makes the outage look like a hang.
    """
    checkouts = []

    class DeadPool:
        @contextmanager
        def connection(self):
            checkouts.append(1)
            raise OperationalError("server closed the connection unexpectedly")
            yield  # pragma: no cover

    monkeypatch.setattr(db, "_pool", DeadPool())
    monkeypatch.setattr(db, "_pool_failed_until", 0.0)
    monkeypatch.setattr(db, "_POOL_RETRY_SECONDS", 30.0)
    monkeypatch.setattr(db, "get_pool", lambda: db._pool)

    first = db.health()
    second = db.health()

    assert first["status"] == "error"
    assert second["status"] == "error"
    assert "retrying" in second["error"]
    assert len(checkouts) == 1
