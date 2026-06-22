# Pushkinskaya Street Tourist Guide — Landmark Recognition System

A fully local tourist landmark identification system for Pushkinskaya Street, Rostov-on-Don, Russia.
No cloud API. No internet at inference time. Everything runs on your machine.

---

## Project structure

```
Tourist_project/
│
├── data/
│   ├── landmarks.json          ← 46 landmarks with GPS coordinates, descriptions, photos
│   ├── photos/                 ← thumbnail images for the frontend (Git LFS)
│   │   ├── pushkin_monument.jpg
│   │   ├── kirov_monument.jpg
│   │   └── ...
│   ├── raw/                    ← training photos (one folder per landmark)
│   └── images/                 ← auto-created by collect_data.py (train/val/test splits)
│
├── models/                     ← auto-created by train.py
│   ├── landmark_classifier.keras
│   └── class_names.json
│
├── frontend/
│   └── index.html              ← tourist-facing web UI (5 tabs, Leaflet map, TTS)
│
├── backend/
│   ├── app.py                  ← Flask REST API
│   └── route_planner.py        ← OSRM walking route logic
│
├── tests/
│   └── test_api.py             ← API unit tests
│
├── .github/workflows/
│   └── ci.yml                  ← GitHub Actions CI/CD
│
├── collect_data.py             ← Step 1: organise photos into splits
├── train.py                    ← Step 2: fine-tune EfficientNetB0
├── evaluate.py                 ← Step 3: confusion matrix + metrics
├── predict.py                  ← quick CLI inference on a single image
├── plan_route.py               ← generate walking routes via OSRM
├── preflight_check.py          ← Docker startup health check
├── requirements.txt            ← full dependencies (training + serving)
├── requirements-serve.txt      ← slim dependencies (production Docker)
├── Dockerfile                  ← container build
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
pip install -r requirements.txt
```

### 3. Start the server

```bash
python backend/app.py
```

Open http://localhost:5000/app in your browser.

### Docker

**Quick start (docker-compose):**
```bash
git lfs pull
# Edit CORS_ORIGINS in docker-compose.yml for your domain
docker compose up -d
```

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

Environment variables:
| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:*` | Pipe-delimited allowed origins |
| `GUNICORN_WORKERS` | `2` | Number of gunicorn worker processes |
| `MODEL_PATH` | `/app/models/landmark_classifier.keras` | Path to model file |

---

## Frontend features

| Tab | Description |
|-----|-------------|
| **Identify** | Upload a photo, get landmark identification with confidence scores |
| **Browse Sites** | Grid of all 46 landmarks with photos, descriptions, fun facts |
| **Near Me** | Uses browser geolocation to find nearby landmarks (with fallback) |
| **Plan a Walk** | Shows OSRM walking route on an interactive Leaflet.js map |
| **Manage Photos** | Upload photos per angle for each landmark (session-only) |

All "Listen" buttons use free browser SpeechSynthesis TTS.

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
| GET    | `/model/info`         | —                            | model training metadata             |
| GET    | `/metrics`            | —                            | Prometheus-compatible metrics       |

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

### Step 4 — Evaluate

```bash
python evaluate.py
```

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
pytest tests/ -v
```

---

## Dependencies

| Package        | Purpose                              |
|----------------|--------------------------------------|
| tensorflow     | EfficientNetB0, training, inference  |
| flask          | REST API server                      |
| flask-cors     | allow browser → API requests         |
| gunicorn       | production WSGI server               |
| pillow         | image loading and preprocessing      |
| numpy          | array operations                     |
| matplotlib     | training curves, confusion matrix    |
| requests       | OSRM routing, HTTP utilities         |
| pytest         | unit tests                           |

Install all: `pip install -r requirements.txt`

For production/Docker (slimmer): `pip install -r requirements-serve.txt`

---

## Data sources

- **Photos**: Yandex Maps (extracted via bookmarklet tool)
- **Geocoding**: Yandex Maps (manual lookup)
- **Routing**: OSRM public demo server — free, no API key
- **Map tiles**: OpenStreetMap — free, attribution required
