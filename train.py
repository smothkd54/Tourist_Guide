"""
train.py
--------
Step 2: fine-tune EfficientNetB0 on the organised landmark photos.

USAGE
-----
  python train.py                        # default settings
  python train.py --epochs-head 5 --epochs-fine 10

WHAT IT DOES
------------
  1. Loads train / val splits from data/images/
  2. Applies aggressive augmentation to compensate for small datasets
  3. Fine-tunes EfficientNetB0 (pretrained on ImageNet):
       Phase 1 — freeze base, train new head  (fast, few epochs)
       Phase 2 — unfreeze top layers, fine-tune end-to-end (careful LR)
  4. Saves:
       models/landmark_classifier.keras   ← full model
       models/class_names.json            ← ordered label list
       models/training_history.json       ← loss / acc curves

REQUIREMENTS
------------
  pip install tensorflow pillow matplotlib
"""

import json
import argparse
import os
from collections import Counter
from pathlib import Path

import tensorflow as tf
import keras
from keras import layers
from keras.applications import EfficientNetB0

from backend.logging_setup import setup_logging

logger = setup_logging("train")

# ── config ──────────────────────────────────────────────────────────────────
DATA_DIR     = Path("data/images")
MODELS_DIR   = Path("models")
IMG_SIZE     = (224, 224)
IMG_EXT      = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
BATCH_SIZE   = 32
EPOCHS_HEAD  = 10       # phase 1: train head only
EPOCHS_FINE  = 20       # phase 2: fine-tune top layers
UNFREEZE_FROM = -30     # unfreeze last N layers of base for phase 2
LR_HEAD      = 1e-3
LR_FINE      = 1e-5
AUTOTUNE     = tf.data.AUTOTUNE
# ────────────────────────────────────────────────────────────────────────────

MODELS_DIR.mkdir(exist_ok=True)


# ── augmentation ─────────────────────────────────────────────────────────────
def build_augmentation():
    return keras.Sequential([
        layers.RandomFlip("horizontal"),
        layers.RandomRotation(0.15),
        layers.RandomZoom(0.15),
        layers.RandomContrast(0.15),
        layers.RandomBrightness(0.10),
        layers.RandomTranslation(0.1, 0.1),
    ], name="augmentation")


# ── dataset loading ───────────────────────────────────────────────────────────
def load_dataset(split: str, batch_size: int, augment: bool = False,
                 data_dir: Path = DATA_DIR):
    split_dir = Path(data_dir) / split
    if not split_dir.exists():
        raise FileNotFoundError(
            f"No '{split}' split found at {split_dir}. "
            "Run collect_data.py first."
        )

    ds = keras.utils.image_dataset_from_directory(
        split_dir,
        image_size=IMG_SIZE,
        batch_size=batch_size,
        label_mode="categorical",
        shuffle=(split == "train"),
        seed=42,
    )
    class_names = ds.class_names

    # Keep pixels in [0, 255]. EfficientNetB0 already contains its own
    # Rescaling(1/255) + Normalization layers; dividing by 255 here fed the
    # network a near-constant vector (~-2.1 after normalisation) and collapsed
    # the model onto a single class.
    ds = ds.map(lambda x, y: (tf.cast(x, tf.float32), y),
                num_parallel_calls=AUTOTUNE)

    if augment:
        aug = build_augmentation()
        ds = ds.map(lambda x, y: (aug(x, training=True), y),
                    num_parallel_calls=AUTOTUNE)

    return ds.prefetch(AUTOTUNE), class_names


# ── model building ────────────────────────────────────────────────────────────
def build_model(num_classes: int, trainable_base: bool = False) -> keras.Model:
    # Try ImageNet weights first (best accuracy).
    # Falls back to random init if the weights CDN is unreachable.
    try:
        base = EfficientNetB0(
            include_top=False,
            weights="imagenet",
            input_shape=(*IMG_SIZE, 3),
        )
        logger.info("Using ImageNet pretrained weights.")
    except Exception:
        logger.warning("Could not download ImageNet weights — training from scratch.")
        logger.info("Transfer learning gives much better results with real photos.")
        base = EfficientNetB0(
            include_top=False,
            weights=None,
            input_shape=(*IMG_SIZE, 3),
        )
    base.trainable = trainable_base

    inputs  = keras.Input(shape=(*IMG_SIZE, 3))
    x       = base(inputs, training=trainable_base)
    x       = layers.GlobalAveragePooling2D()(x)
    x       = layers.BatchNormalization()(x)
    x       = layers.Dropout(0.3)(x)
    x       = layers.Dense(256, activation="relu")(x)
    x       = layers.Dropout(0.3)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)

    return keras.Model(inputs, outputs), base


# ── training ──────────────────────────────────────────────────────────────────
def train(args):
    data_dir = Path(args.data_dir)
    out_dir  = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading datasets from %s ...", data_dir)
    train_ds, class_names = load_dataset("train", args.batch, augment=True, data_dir=data_dir)
    val_ds,   _           = load_dataset("val",   args.batch, augment=False, data_dir=data_dir)
    num_classes = len(class_names)
    logger.info("Classes (%d): %s", num_classes, class_names)

    # save class names now so inference always has them
    with open(out_dir / "class_names.json", "w") as f:
        json.dump(class_names, f, indent=2)

    # Balanced class weights, capped so the 1-3 image classes cannot dominate.
    counts = Counter(
        p.parent.name
        for p in (data_dir / "train").rglob("*")
        if p.is_file() and p.suffix.lower() in IMG_EXT
    )
    total = sum(counts.values())
    class_weight = {
        i: min(total / (num_classes * counts[c]), 3.0)
        for i, c in enumerate(class_names) if counts.get(c)
    }
    logger.info("Class weights: %s",
                {c: round(class_weight[i], 2) for i, c in enumerate(class_names) if counts.get(c)})

    # ── phase 1: head only ────────────────────────────────────────────────
    logger.info("Phase 1 — training classification head (base frozen)...")
    model, base = build_model(num_classes, trainable_base=False)
    model.compile(
        optimizer=keras.optimizers.Adam(LR_HEAD),
        loss=keras.losses.CategoricalCrossentropy(label_smoothing=0.1),
        metrics=["accuracy"],
    )
    model.summary(line_length=80)

    cb_ckpt = keras.callbacks.ModelCheckpoint(
        out_dir / "checkpoint_phase1.keras",
        save_best_only=True, monitor="val_accuracy", verbose=1
    )
    cb_es = keras.callbacks.EarlyStopping(
        patience=5, restore_best_weights=True, monitor="val_accuracy"
    )

    h1 = model.fit(
        train_ds, validation_data=val_ds,
        epochs=args.epochs_head,
        class_weight=class_weight,
        callbacks=[cb_ckpt, cb_es],
    )

    # ── phase 2: fine-tune top layers ─────────────────────────────────────
    logger.info("Phase 2 — fine-tuning top base layers...")
    for layer in base.layers[UNFREEZE_FROM:]:
        if not isinstance(layer, layers.BatchNormalization):
            layer.trainable = True

    model.compile(
        optimizer=keras.optimizers.Adam(LR_FINE),
        loss=keras.losses.CategoricalCrossentropy(label_smoothing=0.1),
        metrics=["accuracy"],
    )

    cb_ckpt2 = keras.callbacks.ModelCheckpoint(
        Path(os.environ.get("MODEL_PATH", str(out_dir / "landmark_classifier.keras"))),
        save_best_only=True, monitor="val_accuracy", verbose=1
    )
    cb_es2 = keras.callbacks.EarlyStopping(
        patience=7, restore_best_weights=True, monitor="val_accuracy"
    )
    cb_lr = keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=3, verbose=1
    )

    h2 = model.fit(
        train_ds, validation_data=val_ds,
        epochs=args.epochs_fine,
        class_weight=class_weight,
        callbacks=[cb_ckpt2, cb_es2, cb_lr],
    )

    # ── save history & plot ───────────────────────────────────────────────
    history = {
        "phase1_acc":     h1.history["accuracy"],
        "phase1_val_acc": h1.history["val_accuracy"],
        "phase1_loss":    h1.history["loss"],
        "phase1_val_loss":h1.history["val_loss"],
        "phase2_acc":     h2.history["accuracy"],
        "phase2_val_acc": h2.history["val_accuracy"],
        "phase2_loss":    h2.history["loss"],
        "phase2_val_loss":h2.history["val_loss"],
    }
    with open(out_dir / "training_history.json", "w") as f:
        json.dump(history, f, indent=2)

    _plot_history(h1, h2, out_dir)

    # ── write model metadata ─────────────────────────────────────────────
    _write_metadata(h1, h2, class_names, args, out_dir, data_dir)

    logger.info("Training complete.")
    logger.info("Model  → %s/landmark_classifier.keras", out_dir)
    logger.info("Labels → %s/class_names.json", out_dir)
    logger.info("Next step:  python evaluate.py")
    logger.info("            python backend/app.py   (to start the API)")


def _plot_history(h1, h2, out_dir: Path = MODELS_DIR):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    all_acc  = h1.history["accuracy"]     + h2.history["accuracy"]
    all_vacc = h1.history["val_accuracy"] + h2.history["val_accuracy"]
    all_loss = h1.history["loss"]         + h2.history["loss"]
    all_vloss= h1.history["val_loss"]     + h2.history["val_loss"]
    ph2_start = len(h1.history["accuracy"])

    axes[0].plot(all_acc,  label="Train acc")
    axes[0].plot(all_vacc, label="Val acc")
    axes[0].axvline(ph2_start, color="grey", linestyle="--", label="Phase 2 start")
    axes[0].set_title("Accuracy")
    axes[0].legend()

    axes[1].plot(all_loss,  label="Train loss")
    axes[1].plot(all_vloss, label="Val loss")
    axes[1].axvline(ph2_start, color="grey", linestyle="--", label="Phase 2 start")
    axes[1].set_title("Loss")
    axes[1].legend()

    plt.tight_layout()
    path = out_dir / "training_curves.png"
    plt.savefig(path, dpi=120)
    logger.info("Curves → %s", path)
    plt.close()


def _count_images(split: str, data_dir: Path = DATA_DIR) -> int:
    split_dir = Path(data_dir) / split
    if not split_dir.exists():
        return 0
    return sum(1 for _ in split_dir.rglob("*") if _.suffix.lower() in IMG_EXT)


def _write_metadata(h1, h2, class_names, args, out_dir: Path = MODELS_DIR,
                    data_dir: Path = DATA_DIR):
    from datetime import datetime, timezone
    model_path = Path(os.environ.get("MODEL_PATH", str(out_dir / "landmark_classifier.keras")))
    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model_file": model_path.name,
        "model_size_bytes": model_path.stat().st_size if model_path.exists() else 0,
        "num_classes": len(class_names),
        "training": {
            "epochs_head": args.epochs_head,
            "epochs_fine": args.epochs_fine,
            "actual_head_epochs": len(h1.history["accuracy"]),
            "actual_fine_epochs": len(h2.history["accuracy"]),
            "batch_size": args.batch,
            "unfreeze_from": UNFREEZE_FROM,
            "lr_head": LR_HEAD,
            "lr_fine": LR_FINE,
        },
        "results": {
            "best_val_acc": round(max(h1.history["val_accuracy"] + h2.history["val_accuracy"]), 4),
            "final_val_acc": round(h2.history["val_accuracy"][-1], 4),
            "final_train_acc": round(h2.history["accuracy"][-1], 4),
            "early_stopped_phase1": len(h1.history["accuracy"]) < args.epochs_head,
            "early_stopped_phase2": len(h2.history["accuracy"]) < args.epochs_fine,
        },
        "data": {
            "train_images": _count_images("train", data_dir),
            "val_images": _count_images("val", data_dir),
            "img_size": list(IMG_SIZE),
        },
    }
    out = out_dir / "model_metadata.json"
    with open(out, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Metadata → %s", out)


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train the Pushkinskaya Street landmark classifier.")
    parser.add_argument("--batch",       type=int, default=BATCH_SIZE)
    parser.add_argument("--epochs-head", type=int, default=EPOCHS_HEAD,  dest="epochs_head")
    parser.add_argument("--epochs-fine", type=int, default=EPOCHS_FINE,  dest="epochs_fine")
    parser.add_argument("--data-dir",    default=str(DATA_DIR), dest="data_dir")
    parser.add_argument("--out-dir",     default=str(MODELS_DIR), dest="out_dir")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
