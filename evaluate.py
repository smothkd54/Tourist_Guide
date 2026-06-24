"""
evaluate.py
-----------
Step 3: evaluate the trained model on the held-out test split.

USAGE
-----
  python evaluate.py
  python evaluate.py --model models/landmark_classifier.keras

OUTPUT
------
  Prints per-class precision / recall / F1 to stdout.
  Saves models/confusion_matrix.png
"""

import json
import argparse
import os
from pathlib import Path

import numpy as np
import tensorflow as tf
import keras
import matplotlib.pyplot as plt

from backend.logging_setup import setup_logging

logger = setup_logging("evaluate")

# ── config ──────────────────────────────────────────────────────────────────
DATA_DIR   = Path("data/images/test")
MODELS_DIR = Path("models")
IMG_SIZE   = (224, 224)
BATCH_SIZE = 32
# ────────────────────────────────────────────────────────────────────────────


def load_class_names() -> list[str]:
    path = MODELS_DIR / "class_names.json"
    if not path.exists():
        raise FileNotFoundError("class_names.json not found. Run train.py first.")
    with open(path) as f:
        return json.load(f)


def load_test_dataset(class_names: list[str]):
    ds = keras.utils.image_dataset_from_directory(
        DATA_DIR,
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="categorical",
        shuffle=False,
    )
    ds = ds.map(lambda x, y: (tf.cast(x, tf.float32) / 255.0, y))
    return ds


def confusion_matrix_manual(y_true, y_pred, n_classes):
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        cm[t][p] += 1
    return cm


def per_class_metrics(cm, class_names):
    print(f"\n{'Class':<24} {'Precision':>10} {'Recall':>10} {'F1':>8} {'Support':>9}")
    print("─" * 65)
    for i, name in enumerate(class_names):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)
        support   = cm[i, :].sum()
        bar = "█" * int(f1 * 20)
        print(f"  {name:<22} {precision:>10.3f} {recall:>10.3f} {f1:>8.3f} {support:>9}  {bar}")


def plot_cm(cm, class_names):
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(class_names)))
    ax.set_xticklabels(class_names, rotation=45, ha="right")
    ax.set_yticks(range(len(class_names)))
    ax.set_yticklabels(class_names)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix — test split")
    thresh = cm.max() / 2
    for i in range(len(class_names)):
        for j in range(len(class_names)):
            ax.text(j, i, str(cm[i, j]),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black", fontsize=9)
    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    out = MODELS_DIR / "confusion_matrix.png"
    plt.savefig(out, dpi=120)
    logger.info("Confusion matrix → %s", out)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path,
                        default=Path(os.environ.get("MODEL_PATH", str(MODELS_DIR / "landmark_classifier.keras"))))
    args = parser.parse_args()
    _run(args.model)


def _run(model_path: Path):
    class_names = load_class_names()
    n_classes   = len(class_names)

    logger.info("Loading model: %s", model_path)
    model = keras.models.load_model(model_path)

    logger.info("Loading test split: %s", DATA_DIR)
    test_ds = load_test_dataset(class_names)

    logger.info("Running inference on test set...")
    y_true_all, y_pred_all = [], []

    for images, labels in test_ds:
        preds = model.predict(images, verbose=0)
        y_true_all.extend(np.argmax(labels.numpy(), axis=1))
        y_pred_all.extend(np.argmax(preds,           axis=1))

    y_true = np.array(y_true_all)
    y_pred = np.array(y_pred_all)

    overall_acc = (y_true == y_pred).mean()
    logger.info("Overall accuracy: %.2f%% (%d/%d)", overall_acc * 100, (y_true == y_pred).sum(), len(y_true))

    cm = confusion_matrix_manual(y_true, y_pred, n_classes)
    per_class_metrics(cm, class_names)
    plot_cm(cm, class_names)

    logger.info("Next step:  python backend/app.py")


if __name__ == "__main__":
    main()
