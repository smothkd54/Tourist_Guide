"""
collect_data.py
---------------
Step 1 of the pipeline: organise your landmark photos into the correct
folder structure so the trainer can find them.

USAGE
-----
  # After adding photos manually to data/raw/<landmark_id>/
  python collect_data.py

  # Or point it at an existing directory of unsorted images:
  python collect_data.py --source /path/to/my/photos

FOLDER STRUCTURE PRODUCED
--------------------------
  data/
    images/
      train/
        annunciation_church/          <- one folder per landmark id
        bostrikiny_house/
        cathedral_nativity/
        chekhov_monument/
        cinema_house/
        don_state_library/
      val/
        annunciation_church/
        ...
      test/
        annunciation_church/
        ...
    raw/                   <- drop your unsorted photos here first

The script copies (does not move) photos and applies an 80/10/10
train/val/test split. It also validates that each class has at
least MIN_PHOTOS_PER_CLASS images before training is attempted.
"""

import json
import random
import shutil
import argparse
from pathlib import Path

from logging_setup import setup_logging

logger = setup_logging("collect_data")

# ── config ──────────────────────────────────────────────────────────────────
DATA_DIR        = Path("data")
RAW_DIR         = DATA_DIR / "raw"
IMAGES_DIR      = DATA_DIR / "images"
LANDMARKS_JSON  = DATA_DIR / "landmarks.json"
SPLITS          = {"train": 0.80, "val": 0.10, "test": 0.10}
MIN_PHOTOS_PER_CLASS = 10          # warn if fewer than this
VALID_EXTENSIONS     = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
SEED = 42
# ────────────────────────────────────────────────────────────────────────────


def load_landmark_ids():
    with open(LANDMARKS_JSON) as f:
        data = json.load(f)
    return [lm["id"] for lm in data["landmarks"]]


def collect_for_landmark(landmark_id: str, source_dir: Path) -> list[Path]:
    """Return all valid image paths found under source_dir/landmark_id/."""
    folder = source_dir / landmark_id
    if not folder.exists():
        return []
    return [
        p for p in folder.rglob("*")
        if p.suffix.lower() in VALID_EXTENSIONS
    ]


def split_and_copy(paths: list[Path], landmark_id: str):
    random.shuffle(paths)
    n = len(paths)
    n_train = int(n * SPLITS["train"])
    n_val   = int(n * SPLITS["val"])

    buckets = {
        "train": paths[:n_train],
        "val":   paths[n_train : n_train + n_val],
        "test":  paths[n_train + n_val :],
    }

    for split, files in buckets.items():
        dest_dir = IMAGES_DIR / split / landmark_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        for i, src in enumerate(files):
            dest = dest_dir / f"{landmark_id}_{split}_{i:04d}{src.suffix.lower()}"
            shutil.move(str(src), str(dest))

    return {k: len(v) for k, v in buckets.items()}


def report(landmark_id: str, counts: dict, total: int):
    status = "OK" if total >= MIN_PHOTOS_PER_CLASS else "WARN"
    logger.info("  %s %s total=%d  train=%d val=%d test=%d",
                status, landmark_id, total,
                counts['train'], counts['val'], counts['test'])


def main(source: Path):
    random.seed(SEED)
    landmark_ids = load_landmark_ids()

    logger.info("Collecting images from: %s", source)
    logger.info("Output → %s", IMAGES_DIR)

    totals = {}
    for lid in landmark_ids:
        paths = collect_for_landmark(lid, source)
        if not paths:
            logger.warning("  %s — no images found in %s", lid, source / lid)
            totals[lid] = 0
            continue
        counts = split_and_copy(paths, lid)
        totals[lid] = len(paths)
        report(lid, counts, len(paths))

    print()
    ready    = sum(1 for t in totals.values() if t >= MIN_PHOTOS_PER_CLASS)
    not_ready = len(landmark_ids) - ready
    logger.info("Summary: %d/%d classes ready for training.", ready, len(landmark_ids))
    if not_ready:
        logger.warning("%d class(es) need more photos (minimum %d each).", not_ready, MIN_PHOTOS_PER_CLASS)
    logger.info("Next step:  python train.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Organise landmark photos for training.")
    parser.add_argument(
        "--source", type=Path, default=RAW_DIR,
        help="Directory containing per-landmark sub-folders (default: data/raw)"
    )
    args = parser.parse_args()
    main(args.source)
