"""
generate_placeholders.py
------------------------
Generates synthetic placeholder images for each landmark class so you
can run the full train → evaluate → serve pipeline immediately, without
waiting for real photos.

Each placeholder is a solid-colour tile with the landmark name and angle
rendered as text.  They are NOT real training data — accuracy will be
meaningless — but the pipeline mechanics (split, augmentation, training
loop, inference endpoint) will all work end-to-end.

Replace the generated images with real photos and re-run train.py.

USAGE
-----
  python generate_placeholders.py              # default 30 images / class
  python generate_placeholders.py --n 50       # more images per class
"""

import argparse
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── config ──────────────────────────────────────────────────────────────────
DATA_DIR       = Path("data")
RAW_DIR        = DATA_DIR / "raw"
LANDMARKS_JSON = DATA_DIR / "landmarks.json"
IMG_SIZE       = (400, 400)

# one distinct background colour per landmark (RGB)
COLOURS = {
    "flatiron":        (42,  58,  82),
    "grand_central":   (72,  48,  36),
    "empire_state":    (36,  60,  50),
    "brooklyn_bridge": (58,  48,  72),
    "chrysler":        (70,  58,  36),
    "statue_of_liberty":(36, 64,  64),
}
# ────────────────────────────────────────────────────────────────────────────


def load_landmarks():
    with open(LANDMARKS_JSON) as f:
        return json.load(f)["landmarks"]


def make_placeholder(landmark_id: str, name: str, angle: str,
                     index: int, colour: tuple) -> Image.Image:
    img  = Image.new("RGB", IMG_SIZE, color=colour)
    draw = ImageDraw.Draw(img)

    # draw a simple geometric shape so images within a class are not identical
    shapes = index % 4
    w, h   = IMG_SIZE
    c      = (min(colour[0]+80, 255), min(colour[1]+80, 255), min(colour[2]+80, 255))
    if shapes == 0:
        draw.rectangle([60, 60, w-60, h-60], outline=c, width=3)
    elif shapes == 1:
        draw.ellipse([60, 60, w-60, h-60], outline=c, width=3)
    elif shapes == 2:
        draw.polygon([(w//2, 60), (w-60, h-60), (60, h-60)], outline=c, width=3)
    else:
        draw.line([(60, 60), (w-60, h-60)], fill=c, width=3)
        draw.line([(w-60, 60), (60, h-60)], fill=c, width=3)

    # add slight random noise so images are not pixel-identical
    noise_layer = Image.new("RGB", IMG_SIZE)
    noise_pixels = noise_layer.load()
    for px in range(IMG_SIZE[0]):
        for py in range(IMG_SIZE[1]):
            r = random.randint(-15, 15)
            noise_pixels[px, py] = (r, r, r)
    img = Image.blend(img.convert("RGBA"), noise_layer.convert("RGBA"), alpha=0.08).convert("RGB")
    draw = ImageDraw.Draw(img)

    # text labels — use default PIL font (no external font needed)
    draw.text((20, 20),  name,  fill=(220, 220, 220))
    draw.text((20, 40),  angle.replace("_", " "), fill=(170, 170, 170))
    draw.text((20, 60),  f"#{index}", fill=(120, 120, 120))
    draw.text((20, h-30), "PLACEHOLDER — replace with real photo",
              fill=(160, 100, 100))

    return img


def main(n_per_class: int):
    landmarks = load_landmarks()

    print(f"\n🖼  Generating {n_per_class} placeholder images per class…\n")

    for lm in landmarks:
        lid    = lm["id"]
        name   = lm["name"]
        angles = lm["angles"]
        colour = COLOURS.get(lid, (50, 50, 70))

        dest = RAW_DIR / lid
        dest.mkdir(parents=True, exist_ok=True)

        for i in range(n_per_class):
            angle = angles[i % len(angles)]
            img   = make_placeholder(lid, name, angle, i, colour)
            path  = dest / f"{lid}_{i:04d}.jpg"
            img.save(path, "JPEG", quality=85)

        print(f"  ✅ {lid:<25} → {n_per_class} images in {dest}")

    print(f"\nDone. Now run:\n")
    print(f"  python collect_data.py      # split into train/val/test")
    print(f"  python train.py             # train the model")
    print(f"  python evaluate.py          # check metrics")
    print(f"  python backend/app.py       # serve the API\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30,
                        help="Number of placeholder images per landmark class (default 30)")
    args = parser.parse_args()
    main(args.n)
