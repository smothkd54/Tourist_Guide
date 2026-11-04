# Contributing

The primary repository is on GitVerse (see `docs/gitverse.md`); GitHub is a
mirror. This file covers the local workflow that both CIs enforce.

## Prerequisites

- Python 3.11+
- Docker Desktop (for PostgreSQL and the composed stack)
- Android SDK + JDK 21 (only for the Android app)

## Backend setup

```bash
git lfs install
git lfs pull
pip install -e ".[dev]"
```

`pip install -e ".[dev]"` installs the serving stack, PostgreSQL drivers,
migrations, pytest, ruff and matplotlib. TensorFlow is only needed for training,
but the current test suite imports Keras in one smoke test, so keep the full
install for local runs.

## PostgreSQL

Start the database and create the environment file:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(32))"   # ADMIN_TOKEN
python -c "import secrets; print(secrets.token_urlsafe(32))"   # METRICS_TOKEN
docker compose up -d db
```

Set `DATABASE_URL` in `.env` to the host-side URL, then migrate and seed:

```bash
export DATABASE_URL=postgresql://pushkinskaya:<password>@127.0.0.1:5432/pushkinskaya
alembic upgrade head
python scripts/seed_db.py
```

`scripts/seed_db.py` is idempotent. `--if-empty` is used by the container
entrypoint; `--check` verifies counts without writing.

The API falls back to `data/*.json` when `DATABASE_URL` is unset. That fallback
is for development and for the JSON-mode test run, not for deployments.

## Tests — run both modes

```bash
# JSON fallback: no database needed
pytest tests -q

# PostgreSQL: use a database whose name ends in `_test`
createdb pushkinskaya_test          # once
export DATABASE_URL=postgresql://pushkinskaya:<password>@127.0.0.1:5432/pushkinskaya_test
alembic upgrade head
python scripts/seed_db.py
pytest tests -q
```

`tests/test_db.py` truncates `reports`, `itineraries` and `itinerary_items`
between tests. It refuses to run against a database that does not end in
`_test` unless `ALLOW_DB_TESTS=1` is set explicitly — never point it at the
development database.

## Schema changes

1. Edit the model/migration only through a new Alembic revision:

   ```bash
   alembic revision -m "describe the change"
   ```

2. Write `upgrade()` and a real `downgrade()`.
3. Apply it to both the development and test databases.
4. Add or update a test in `tests/test_db.py` for constraints that matter.
5. Never edit an applied migration; a deployed database has already recorded
   its revision.

## Lint

```bash
ruff check .
```

CI pins `ruff==0.15.18`; run the same version to avoid surprises.

## Android

```bash
cd android
gradlew.bat assembleDebug          # Windows
./gradlew assembleDebug            # Linux/macOS

# With the phone over USB:
adb reverse tcp:5000 tcp:5000
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

Builds are debug-signed and sideloaded; Google Play is not used. Add new
user-facing text to both `res/values/strings.xml` and
`res/values-ru/strings.xml`.

## Content rules

- Publish a photo only when the author, licence, licence URL and source page
  are verified. `scripts/audit_photo_licenses.py` is the gate.
- Show the credit next to the photo in every client.
- If no free-licensed photo of the actual object exists, ship the text-only
  entry. A missing photo is better than a wrong one.
- Placeholder or synthetic photos must never reach `data/photos/`.

## Commits and merge requests

- Keep each commit to one concern; the history is part of the deliverable.
- Say what changed and why in the body when the reason is not obvious.
- Open a merge request against `main`; CI must pass.
- Do not commit `.env`, tokens, training images, or `*.keras` outside LFS.

## Deployment checklist

- `docker compose up -d --build`
- `/` reports `status: ok` and `data_source: postgres`
- `python scripts/admin.py stats` matches the expected counts (46 landmarks,
  29 classes, 38 published photos)
- A report posted from the web UI appears in `python scripts/admin.py reports`
- A shared itinerary link reopens the same route
