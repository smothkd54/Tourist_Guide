# Pushkinskaya Street Tourist Guide — Landmark Recognition System

A fully local tourist landmark identification system for Pushkinskaya Street, Rostov-on-Don, Russia.
No cloud API. No internet at inference time. Everything runs on your machine.

---

## Project structure

```
Tourist_project/
│
├── backend/
│   ├── __init__.py              ← package marker
│   ├── app.py                   ← Flask REST API, CORS, rate limiter, health
│   ├── logging_setup.py         ← shared logging (RotatingFileHandler, 5 MB × 3)
│   └── route_planner.py         ← OSRM walking route logic
│
├── frontend/
│   ├── index.html               ← tourist-facing web UI (6 tabs, Leaflet map, TTS)
│   ├── manifest.json            ← PWA manifest (standalone, dark theme)
│   └── static/
│       └── leaflet/
│           ├── leaflet.js       ← self-hosted Leaflet (no CDN)
│           └── leaflet.css
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              ← shared fixtures (client, client_with_mock_model)
│   └── test_api.py              ← 32 API tests
│
├── scripts/
│   └── backup.sh                ← daily backup (models, data, logs)
│
├── data/
│   ├── landmarks.json           ← 46 landmarks with GPS coordinates, descriptions, photos
│   ├── photos/                  ← thumbnail images for the frontend (Git LFS)
│   ├── raw/                     ← training photos (one folder per landmark)
│   └── images/                  ← auto-created by collect_data.py (train/val/test splits)
│
├── models/                      ← auto-created by train.py
│   ├── landmark_classifier.keras
│   ├── class_names.json
│   └── model_metadata.json
│
├── .github/workflows/
│   └── ci.yml                   ← lint (ruff), tests, Docker build, Trivy scan
│
├── sw.js                        ← service worker (root scope, offline cache + predict queue)
├── Caddyfile                    ← reverse proxy (auto-HTTPS, gzip, caching)
├── pyproject.toml               ← package config, entry points, deps, ruff/pytest
├── requirements.txt             ← full dependencies (training + serving)
├── requirements-serve.txt       ← slim dependencies (production Docker)
├── Dockerfile                   ← container build (gunicorn, healthcheck, non-root)
├── docker-compose.yml           ← Caddy + web services
├── .env.example                 ← environment variable template
├── collect_data.py              ← Step 1: organise photos into splits
├── train.py                     ← Step 2: fine-tune EfficientNetB0
├── evaluate.py                  ← Step 3: confusion matrix + metrics
├── predict.py                   ← quick CLI inference on a single image
├── plan_route.py                ← generate walking routes via OSRM
├── preflight_check.py           ← Docker startup health check
└── README.md
```

---

## Quick start

### 1. Clone with Git LFS (for images)

```bash
git lfs install
git clone https://github.com/smothkd54/Tourist_Guide.git
cd Tourist_Guide
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

This installs the package in editable mode with all training, testing, and linting dependencies.

For production/Docker (slimmer, no matplotlib/opencv):
```bash
pip install -r requirements-serve.txt
```

### 3. Start the server

```bash
python backend/app.py
```

Open http://localhost:5000/app in your browser.

### CLI entry points

After `pip install -e ".[dev]"`, these commands are available:

| Command | What it does |
|---------|-------------|
| `pushkinskaya-train` | Fine-tune EfficientNetB0 |
| `pushkinskaya-evaluate` | Generate confusion matrix + metrics |
| `pushkinskaya-predict` | CLI inference on a single image |
| `pushkinskaya-collect` | Organise raw photos into train/val/test splits |
| `pushkinskaya-plan` | Generate a walking route via OSRM |
| `pushkinskaya-preflight` | Verify model + data before starting server |

### Docker

**Quick start (docker-compose):**
```bash
git lfs pull
cp .env.example .env
# Edit .env for your domain (CORS_ORIGINS, etc.)
docker compose up -d
```

This starts:
- **Caddy** (ports 80/443) — reverse proxy with auto-HTTPS via Let's Encrypt
- **web** (port 5000 internal) — Flask + gunicorn backend

**Manual (docker run):**
```bash
git lfs pull
docker build -t pushkinskaya-explorer .
docker run -p 5000:5000 \
  -e CORS_ORIGINS=https://your-domain.com \
  pushkinskaya-explorer
```

**Swap model without rebuild:**
```bash
cp new_model.keras ./models/landmark_classifier.keras
docker compose restart
```

**Environment variables (.env):**

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:*` | Pipe-delimited allowed origins |
| `GUNICORN_WORKERS` | `2` | Number of gunicorn worker processes |
| `MODEL_PATH` | `/app/models/landmark_classifier.keras` | Path to model file |
| `LOG_DIR` | `/app/logs` | Directory for log files |

---

## Frontend features

| Tab | Description |
|-----|-------------|
| **Identify** | Upload a photo, get landmark identification with confidence scores |
| **Browse Sites** | Grid of all 46 landmarks with photos, descriptions, fun facts |
| **Near Me** | Uses browser geolocation to find nearby landmarks (with fallback) |
| **Plan a Walk** | Shows OSRM walking route on an interactive Leaflet.js map |
| **Manage Photos** | Upload photos per angle for each landmark (session-only) |

Additional features:
- **PWA offline support** — service worker caches landmarks, photos, and model info for offline use
- **Offline predict queue** — queue up to 5 predictions while offline; auto-processes when connection returns
- **Russian language toggle** — switch between EN/RU for landmark names (persisted in localStorage)
- **Self-hosted Leaflet** — map library served locally, no CDN dependency
- All "Listen" buttons use free browser SpeechSynthesis TTS

---

## API reference

| Method | Endpoint              | Body / Params                | Returns                              |
|--------|-----------------------|------------------------------|--------------------------------------|
| GET    | `/`                   | —                            | health check + model status          |
| GET    | `/landmarks`          | —                            | array of all 46 landmark objects     |
| GET    | `/landmarks/<id>`     | —                            | single landmark object               |
| GET    | `/nearby`             | `lat`, `lon`, `radius_m`     | landmarks within radius              |
| GET    | `/plan`               | `start`, `minutes`, `visit`  | dynamic walking route via OSRM       |
| POST   | `/plan-custom`        | `{ landmarks, start }`       | custom walking route via OSRM        |
| GET    | `/route`              | —                            | pre-planned OSRM walking route       |
| GET    | `/photo/<id>`         | —                            | thumbnail image for a landmark       |
| GET    | `/photos/available`   | —                            | list of landmark IDs with photos     |
| POST   | `/predict`            | `{ "image": "<base64>" }`    | prediction + landmark info           |
| GET    | `/model/info`         | —                            | model training metadata              |
| GET    | `/metrics`            | —                            | Prometheus-compatible metrics        |
| GET    | `/sw.js`              | —                            | service worker script                |

Health check returns `503` (not `200`) when the model is missing or a LFS pointer stub.

---

## Training pipeline

### Step 1 — Collect photos

Place your photos in `data/raw/<landmark_id>/`. Aim for at least 10 photos per landmark.

### Step 2 — Organise splits

```bash
python collect_data.py
```

Splits photos 80% train / 10% val / 10% test.

### Step 3 — Train

```bash
python train.py --epochs-head 10 --epochs-fine 20
```

Options:
```
--batch       INT   batch size (default 32)
--epochs-head INT   phase 1 epochs, head only (default 10)
--epochs-fine INT   phase 2 epochs, fine-tune (default 20)
```

Training uses EfficientNetB0 (pretrained on ImageNet) with two phases:
- **Phase 1**: classification head only (base frozen)
- **Phase 2**: top layers unfrozen, end-to-end fine-tune

After training, `models/model_metadata.json` is written with class count, accuracy, training timestamps, and hyperparameters.

### Step 4 — Evaluate

```bash
python evaluate.py
```

Generates confusion matrix (`models/confusion_matrix.png`) and training curves (`models/training_curves.png`).

### Step 5 — Plan a walking route

```bash
python plan_route.py --minutes 60 --start pushkin_monument
```

Uses OSRM public API for real walking routes.

---

## Adding a new landmark

1. Add an entry to `data/landmarks.json` following the existing schema.
2. Create `data/raw/<new_id>/` and add at least 10 photos.
3. Place a thumbnail in `data/photos/<new_id>.jpg`.
4. Re-run `collect_data.py` then `train.py`.

---

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

32 tests covering:
- **Health** — model status, LFS pointer detection, degraded health returns 503
- **Landmarks** — list, single, filter, invalid ID
- **Nearby** — radius filter, missing params
- **Predict** — empty body, base64 decoding, threshold enforcement, real-model smoke test
- **Route planning** — OSRM integration, rate limiter, custom route validation
- **Photos** — serve, available list
- **Frontend** — serve index.html
- **Model info** — metadata endpoint
- **Logging** — log file creation
- **Metrics** — Prometheus counters

Shared fixtures live in `tests/conftest.py` (`client`, `client_with_mock_model`).

---

## Linting

```bash
ruff check .
```

Configured in `pyproject.toml`: line length 120, target Python 3.10.

---

## Dependencies

### Installation via pyproject.toml (recommended)

```bash
pip install -e ".[dev]"     # full (training + testing + linting)
pip install -e .             # production only
```

### Core packages

| Package | Purpose |
|---------|---------|
| tensorflow | EfficientNetB0, training, inference |
| keras | model building (standalone Keras 3) |
| flask | REST API server |
| flask-cors | allow browser → API requests |
| gunicorn | production WSGI server |
| pillow | image loading and preprocessing |
| numpy | array operations |
| requests | OSRM routing, HTTP utilities |

### Training-only packages

| Package | Purpose |
|---------|---------|
| matplotlib | training curves, confusion matrix |
| opencv-python | image preprocessing |
| imagehash | deduplication |
| beautifulsoup4 | data collection |

### Development packages

| Package | Purpose |
|---------|---------|
| pytest | unit tests |
| ruff | linting |

### Docker (slim)

```bash
pip install -r requirements-serve.txt
```

Includes tensorflow, flask, gunicorn, pillow, numpy, requests. Excludes matplotlib, opencv, imagehash, pytest.

---

## PWA & offline support

The app is a Progressive Web App. The service worker (`sw.js`) runs at root scope (`/`) and caches:

- **App shell** — `/app` (HTML, JS, CSS)
- **Landmarks** — `/landmarks` (cache-first)
- **Photos** — `/photo/*` (cache-first)
- **Model info** — `/model/info` (cache-first)

### Offline predict queue

When offline, predictions are queued in `localStorage` (5-item cap). Each item stores the base64 image and status (`queued` → `processing` → `done`/`failed`). When the browser comes back online:

1. Queue items auto-process in order
2. Results appear in both the main result card and the queue panel
3. Completed items are auto-pruned on `QuotaExceeded`

### Cache versioning

The SW cache is versioned (`pushkinskaya-v1` in `sw.js`). Increment the version string to bust all caches on update.

---

## Production deployment

### Caddy reverse proxy

The `Caddyfile` configures Caddy as a reverse proxy in front of gunicorn:

- **Auto-HTTPS** — Let's Encrypt provisioning (just point your DNS A record)
- **gzip** — compresses all responses
- **Cache-Control headers** — static assets cached 24h, API responses not cached

For local development, Caddy listens on `:80` (plain HTTP). For production HTTPS, uncomment the domain block in `Caddyfile` and replace `your-domain.com`.

### Docker Compose

```bash
cp .env.example .env
# Edit .env for your deployment
docker compose up -d
```

Services:
- **caddy** — ports 80/443, reverse proxy
- **web** — port 5000 (internal), Flask + gunicorn

### Health check

The Docker container includes a health check:
```
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3
    CMD curl -f http://localhost:5000/ || exit 1
```

The `/` endpoint returns `503` when the model is missing or a LFS pointer stub.

---

## Logging

All scripts use `backend/logging_setup.py` for dual-output logging:

- **Console** — stderr, with emojis, INFO level
- **File** — `logs/<script_name>.log`, RotatingFileHandler (5 MB × 3 backups), emoji-stripped, UTF-8

Set `LOG_DIR` to change the log directory (default: `logs/`).

---

## Monitoring

### Prometheus metrics

`GET /metrics` returns Prometheus-compatible counters:

| Metric | Type | Description |
|--------|------|-------------|
| `pushkinskaya_http_requests_total` | counter | HTTP requests by endpoint and status |
| `pushkinskaya_prediction_confidence` | histogram | Prediction confidence distribution |
| `pushkinskaya_osrm_requests_total` | counter | OSRM routing requests |
| `pushkinskaya_uptime_seconds` | gauge | Process uptime |

Metrics are per-worker, in-memory. Counters reset on worker restart — suitable for container metrics shipped to Prometheus/Grafana.

---

## Backup & recovery

```bash
./scripts/backup.sh              # backup to /var/backups/pushkinskaya
./scripts/backup.sh /mnt/backup  # backup to custom directory
```

Backs up:
- `models/` — trained model + metadata
- `data/` — landmarks.json, photos (excludes raw/ and images/)
- `logs/` — all log files

Retains 7 days of backups. Cron example (daily at 3 AM):
```
0 3 * * * /path/to/tourist_app/scripts/backup.sh /mnt/backup >> /var/log/tourist-backup.log 2>&1
```

---

## CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`):

1. **Lint** — `ruff check .` (all Python files)
2. **Test** — `pytest tests/ -v` (32 tests)
3. **Docker build** — builds image, runs preflight check
4. **Trivy scan** — fails on CRITICAL/HIGH vulnerabilities

---

## Data sources

- **Photos**: Yandex Maps (extracted via bookmarklet tool)
- **Geocoding**: Yandex Maps (manual lookup)
- **Routing**: OSRM public demo server — free, no API key, rate-limited
- **Map tiles**: OpenStreetMap — free, attribution required
- **Map library**: Leaflet.js — self-hosted in `frontend/static/leaflet/`
