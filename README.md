# NYC Street Explorer — Landmark Recognition System

A fully local tourist landmark identification system.
No cloud API. No internet at inference time. Everything runs on your machine.

---

## Project structure

```
nyc_explorer/
│
├── data/
│   ├── landmarks.json          ← landmark metadata (descriptions, facts)
│   ├── raw/                    ← DROP YOUR PHOTOS HERE (one folder per landmark)
│   │   ├── flatiron/
│   │   ├── grand_central/
│   │   ├── empire_state/
│   │   ├── brooklyn_bridge/
│   │   ├── chrysler/
│   │   └── statue_of_liberty/
│   └── images/                 ← auto-created by collect_data.py
│       ├── train/
│       ├── val/
│       └── test/
│
├── models/                     ← auto-created by train.py
│   ├── landmark_classifier.keras
│   ├── class_names.json
│   ├── training_history.json
│   └── training_curves.png
│
├── frontend/
│   └── index.html              ← tourist-facing web UI
│
├── backend/
│   └── app.py                  ← Flask REST API
│
├── collect_data.py             ← Step 1: organise photos into splits
├── generate_placeholders.py    ← Step 1b: make synthetic images for testing
├── train.py                    ← Step 2: fine-tune EfficientNetB0
├── evaluate.py                 ← Step 3: confusion matrix + metrics
├── predict.py                  ← quick CLI inference on a single image
└── requirements.txt
```

---

## Quick start (with placeholder images)

Use this path to verify the whole pipeline works before you have real photos.

```bash
# 1. install dependencies
pip install -r requirements.txt

# 2. generate synthetic placeholder images (30 per class)
python generate_placeholders.py

# 3. organise into train / val / test splits
python collect_data.py

# 4. train (placeholders only — accuracy will be low, pipeline verified)
python train.py --epochs-head 5 --epochs-fine 5

# 5. evaluate on test split
python evaluate.py

# 6. start the API
python backend/app.py

# 7. open the tourist UI
#    → open frontend/index.html in your browser
#    OR visit http://localhost:5000/app
```

---

## Production path (with real photos)

### Step 1 — Collect photos

For each landmark, photograph it from multiple angles (minimum 10, ideally 50+):

| Landmark           | Required angles                                      |
|--------------------|------------------------------------------------------|
| flatiron           | front, north_tip, aerial, broadway_side              |
| grand_central      | main_facade, concourse_ceiling, south_entrance, aerial |
| empire_state       | 34th_st_face, 5th_ave_face, night_shot, aerial, from_below |
| brooklyn_bridge    | manhattan_tower, brooklyn_tower, pedestrian_walkway, under_bridge |
| chrysler           | street_level, midtown_skyline, crown_detail, lobby   |
| statue_of_liberty  | harbor_view, face_closeup, rear, torch_detail, from_ferry |

Place photos in `data/raw/<landmark_id>/`. Any filename is fine.

```
data/raw/
  flatiron/
    IMG_0001.jpg
    IMG_0002.jpg
    ...
  grand_central/
    photo_001.jpg
    ...
```

### Step 2 — Organise splits

```bash
python collect_data.py
```

This shuffles and splits your photos 80% train / 10% val / 10% test.
It warns you if any class has fewer than 10 images.

### Step 3 — Train

```bash
python train.py
```

Options:
```
--batch       INT   batch size (default 32, reduce to 8 if GPU memory limited)
--epochs-head INT   phase 1 epochs, head only (default 10)
--epochs-fine INT   phase 2 epochs, fine-tune (default 20)
```

Training runs in two phases:
- **Phase 1**: EfficientNetB0 base frozen, only the new classification head trains. Fast.
- **Phase 2**: Top 30 layers of base unfrozen, end-to-end fine-tune at low learning rate.

Early stopping and checkpoint saving are automatic. The best model is saved to
`models/landmark_classifier.keras`.

### Step 4 — Evaluate

```bash
python evaluate.py
```

Prints per-class precision, recall, F1 on the held-out test split.
Saves `models/confusion_matrix.png`.

### Step 5 — Serve

```bash
python backend/app.py
```

Then open `frontend/index.html` in any browser.

---

## API reference

| Method | Endpoint            | Body / Params            | Returns                              |
|--------|---------------------|--------------------------|--------------------------------------|
| GET    | `/`                 | —                        | health check + model status          |
| GET    | `/landmarks`        | —                        | array of all landmark objects        |
| GET    | `/landmarks/<id>`   | —                        | single landmark object               |
| POST   | `/predict`          | `{ "image": "<base64>" }`| prediction + landmark info           |

### POST /predict — example response (identified)

```json
{
  "identified": true,
  "landmark_id": "flatiron",
  "name": "Flatiron Building",
  "confidence": 0.923,
  "confidence_pct": "92.3%",
  "top5": [
    { "landmark_id": "flatiron",    "confidence": 0.923 },
    { "landmark_id": "empire_state","confidence": 0.041 },
    ...
  ],
  "info": {
    "id": "flatiron",
    "name": "Flatiron Building",
    "street": "175 Fifth Ave, New York, NY 10010",
    "year_built": 1902,
    "type": "Architecture",
    "architect": "Daniel Burnham",
    "style": "Beaux-Arts",
    "height_ft": 285,
    "floors": 22,
    "description": "...",
    "fun_fact": "...",
    "angles": ["front", "north_tip", "aerial", "broadway_side"]
  }
}
```

### POST /predict — low confidence response

```json
{
  "identified": false,
  "message": "Confidence too low — try a clearer photo or different angle.",
  "confidence": 0.21,
  "top5": [ ... ]
}
```

---

## Adding a new landmark

1. Add an entry to `data/landmarks.json` following the existing schema.
2. Create `data/raw/<new_id>/` and add at least 10 photos.
3. Re-run `collect_data.py` then `train.py`.
4. The new class appears automatically in the frontend.

Military buildings are excluded by design — simply do not add them to
`landmarks.json` or to `data/raw/`.

---

## Tips for better accuracy

- **More photos = better accuracy.** Aim for 100+ per class.
- **Vary conditions**: different times of day, weather, seasons, distances.
- **Cover all angles** listed in `landmarks.json`.
- **Balance classes**: try to keep photo counts roughly equal across landmarks.
- If accuracy stalls below 80%, increase `--epochs-fine` or reduce `--batch`.

---

## Dependencies

| Package        | Purpose                              |
|----------------|--------------------------------------|
| tensorflow     | EfficientNetB0, training, inference  |
| flask          | REST API server                      |
| flask-cors     | allow browser → API requests         |
| pillow         | image loading and preprocessing      |
| numpy          | array operations                     |
| matplotlib     | training curves, confusion matrix    |

Install all: `pip install -r requirements.txt`
