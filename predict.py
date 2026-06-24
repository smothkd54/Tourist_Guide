"""
predict.py
----------
Run inference on a single image from the command line.
Useful for quick spot-checks without starting the Flask server.

USAGE
-----
  python predict.py path/to/photo.jpg
  python predict.py path/to/photo.jpg --top 5
  python predict.py path/to/photo.jpg --model models/my_model.keras
"""

import json
import argparse
import os
from pathlib import Path

import numpy as np
from PIL import Image
import keras

from backend.logging_setup import setup_logging

logger = setup_logging("predict")

# ── config ──────────────────────────────────────────────────────────────────
MODELS_DIR   = Path("models")
DATA_DIR     = Path("data")
IMG_SIZE     = (224, 224)
THRESHOLD    = 0.40
# ────────────────────────────────────────────────────────────────────────────


def load_resources(model_path: Path):
    cn_path = MODELS_DIR / "class_names.json"
    lm_path = DATA_DIR / "landmarks.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}\nRun train.py first.")
    if not cn_path.exists():
        raise FileNotFoundError("class_names.json not found. Run train.py first.")

    model       = keras.models.load_model(model_path)
    class_names = json.loads(cn_path.read_text())

    landmarks_by_id = {}
    if lm_path.exists():
        data = json.loads(lm_path.read_text())
        landmarks_by_id = {lm["id"]: lm for lm in data["landmarks"]}

    return model, class_names, landmarks_by_id


def preprocess(image_path: Path) -> np.ndarray:
    img = Image.open(image_path).convert("RGB").resize(IMG_SIZE, Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


def predict(image_path: Path, model, class_names, landmarks_by_id, top_n: int):
    tensor = preprocess(image_path)
    probs  = model.predict(tensor, verbose=0)[0]

    top_idx = np.argsort(probs)[::-1][:top_n]

    logger.info("Image: %s", image_path)
    print(f"{'Rank':<6} {'Landmark ID':<26} {'Confidence':>12}  Bar")
    print("─" * 65)

    for rank, idx in enumerate(top_idx, 1):
        lid   = class_names[idx]
        conf  = probs[idx]
        bar   = "█" * int(conf * 40)
        mark  = " ✅" if rank == 1 and conf >= THRESHOLD else (" ⚠️ low" if rank == 1 else "")
        print(f"  {rank:<4} {lid:<26} {conf:>11.3f}  {bar}{mark}")

    print()

    best_id   = class_names[top_idx[0]]
    best_conf = float(probs[top_idx[0]])

    if best_conf < THRESHOLD:
        logger.warning("Confidence %.1f%% is below threshold %d%%.", best_conf * 100, THRESHOLD * 100)
        print(f"⚠️  Confidence {best_conf:.1%} is below threshold {THRESHOLD:.0%}.")
        print("   Try a clearer or less cropped photo, or add more training images.")
    else:
        info = landmarks_by_id.get(best_id, {})
        logger.info("Identified: %s (confidence: %.3f)", info.get("name", best_id), best_conf)
        print(f"✅  Identified: {info.get('name', best_id)}")
        if info:
            print(f"   Street  : {info.get('street', '—')}")
            print(f"   Built   : {info.get('year_built', '—')}")
            print(f"   Type    : {info.get('type', '—')}")
            if info.get("fun_fact"):
                print(f"   ★ {info['fun_fact']}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Predict Pushkinskaya Street landmark from an image.")
    parser.add_argument("image", type=Path, help="Path to image file")
    parser.add_argument("--top",   type=int,  default=3,
                        help="Show top-N predictions (default 3)")
    parser.add_argument("--model", type=Path,
                        default=Path(os.environ.get("MODEL_PATH", str(MODELS_DIR / "landmark_classifier.keras"))),
                        help="Path to trained model")
    args = parser.parse_args()

    model, class_names, landmarks_by_id = load_resources(args.model)
    predict(args.image, model, class_names, landmarks_by_id, args.top)


if __name__ == "__main__":
    main()
