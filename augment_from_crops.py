"""
augment_from_crops.py
---------------------
You have one image containing multiple landmarks.
This script:
  1. Opens your image and lets you draw a crop box around each landmark
  2. Saves each crop as a clean source image
  3. Generates N augmented variants of each crop into data/raw/<landmark_id>/

USAGE
-----
  python augment_from_crops.py --image path/to/your/photo.jpg --n 60

  A window opens. For each landmark:
    - Draw a rectangle around it with your mouse
    - A menu asks which landmark it is
    - Repeat for all landmarks in the image
    - Press Q when done

REQUIREMENTS
------------
  pip install opencv-python pillow numpy
"""

import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

DATA_DIR       = Path("data")
RAW_DIR        = DATA_DIR / "raw"
LANDMARKS_JSON = DATA_DIR / "landmarks.json"

# ── augmentation config ───────────────────────────────────────────────────────
AUG_CONFIG = {
    "rotation_range":    (-25, 25),
    "zoom_range":        (0.75, 1.25),
    "brightness_range":  (0.5, 1.6),
    "contrast_range":    (0.6, 1.6),
    "saturation_range":  (0.6, 1.5),
    "hflip_prob":        0.5,
    "blur_prob":         0.2,
    "noise_prob":        0.3,
    "output_size":       (400, 400),
}


def load_landmarks():
    with open(LANDMARKS_JSON) as f:
        data = json.load(f)
    return [(lm["id"], lm["name"]) for lm in data["landmarks"]]


# ── augmentation ──────────────────────────────────────────────────────────────
def augment_image(pil_img: Image.Image, cfg: dict) -> Image.Image:
    img = pil_img.copy().convert("RGB")

    # horizontal flip
    if random.random() < cfg["hflip_prob"]:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)

    # rotation
    angle = random.uniform(*cfg["rotation_range"])
    img = img.rotate(angle, expand=True, fillcolor=(128, 128, 128))

    # zoom / crop
    zoom = random.uniform(*cfg["zoom_range"])
    w, h = img.size
    new_w, new_h = int(w * zoom), int(h * zoom)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    # centre-crop back to a square
    left   = max(0, (new_w - w) // 2)
    top    = max(0, (new_h - h) // 2)
    right  = left + min(w, new_w)
    bottom = top  + min(h, new_h)
    img = img.crop((left, top, right, bottom))

    # brightness
    factor = random.uniform(*cfg["brightness_range"])
    img = ImageEnhance.Brightness(img).enhance(factor)

    # contrast
    factor = random.uniform(*cfg["contrast_range"])
    img = ImageEnhance.Contrast(img).enhance(factor)

    # saturation
    factor = random.uniform(*cfg["saturation_range"])
    img = ImageEnhance.Color(img).enhance(factor)

    # blur
    if random.random() < cfg["blur_prob"]:
        radius = random.uniform(0.5, 1.5)
        img = img.filter(ImageFilter.GaussianBlur(radius))

    # noise
    if random.random() < cfg["noise_prob"]:
        arr = np.array(img, dtype=np.int16)
        noise = np.random.randint(-20, 20, arr.shape, dtype=np.int16)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

    # final resize
    img = img.resize(cfg["output_size"], Image.LANCZOS)
    return img


def generate_augmented(source_pil: Image.Image, landmark_id: str, n: int):
    dest = RAW_DIR / landmark_id
    dest.mkdir(parents=True, exist_ok=True)

    # find starting index so we don't overwrite existing images
    existing = list(dest.glob("*.jpg"))
    start_idx = len(existing)

    for i in range(n):
        aug = augment_image(source_pil, AUG_CONFIG)
        path = dest / f"{landmark_id}_aug_{start_idx + i:04d}.jpg"
        aug.save(path, "JPEG", quality=90)

    print(f"  ✅ {landmark_id:<26} → {n} augmented images saved to {dest}")


# ── interactive crop UI ───────────────────────────────────────────────────────
class CropSelector:
    def __init__(self, image_path: Path):
        self.image_path = image_path
        self.img_bgr    = cv2.imread(str(image_path))
        if self.img_bgr is None:
            raise FileNotFoundError(f"Cannot open image: {image_path}")

        # scale down for display if very large
        h, w = self.img_bgr.shape[:2]
        self.scale = min(1.0, 1200 / max(w, h))
        dw, dh = int(w * self.scale), int(h * self.scale)
        self.display = cv2.resize(self.img_bgr, (dw, dh))

        self.crops   = []   # list of (landmark_id, PIL.Image)
        self.roi     = None

    def _select_roi(self) -> tuple | None:
        """Let the user draw a rectangle. Returns (x,y,w,h) in original coords or None."""
        clone = self.display.copy()
        cv2.putText(clone,
                    "Draw box around landmark, press SPACE/ENTER to confirm, C to cancel",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        roi = cv2.selectROI("NYC Explorer — crop selector", clone,
                            fromCenter=False, showCrosshair=True)
        cv2.destroyAllWindows()
        if roi == (0, 0, 0, 0):
            return None
        # scale back to original image coordinates
        x, y, rw, rh = roi
        return (int(x / self.scale), int(y / self.scale),
                int(rw / self.scale), int(rh / self.scale))

    def _pick_landmark(self, landmarks: list) -> str | None:
        """Print a numbered menu and return the chosen landmark id."""
        print("\n  Which landmark did you crop?")
        for i, (lid, name) in enumerate(landmarks, 1):
            print(f"    {i}) {name}  [{lid}]")
        print("    0) Skip / redo")
        while True:
            choice = input("  Enter number: ").strip()
            if choice == "0":
                return None
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(landmarks):
                    return landmarks[idx][0]
            except ValueError:
                pass
            print("  Invalid — try again.")

    def run(self, landmarks: list) -> list:
        """
        Interactive loop. Returns list of (landmark_id, PIL.Image) for each crop.
        """
        print("\n📸 Image loaded:", self.image_path)
        print("   Draw a box around each landmark in the image.")
        print("   Press Q in the main window (or Ctrl+C here) when finished.\n")

        while True:
            # show current state
            preview = self.display.copy()
            for i, (lid, _) in enumerate(self.crops):
                cv2.putText(preview, f"#{i+1} {lid}", (10, 50 + i*24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
            cv2.putText(preview,
                        f"Crops so far: {len(self.crops)}  |  Press Q to finish",
                        (10, self.display.shape[0] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 100), 2)
            cv2.imshow("NYC Explorer — crop selector", preview)
            key = cv2.waitKey(0) & 0xFF

            if key == ord('q') or key == ord('Q'):
                cv2.destroyAllWindows()
                break

            # any other key → select new ROI
            cv2.destroyAllWindows()
            roi = self._select_roi()
            if roi is None:
                print("  Cancelled, try again.")
                continue

            x, y, rw, rh = roi
            if rw < 20 or rh < 20:
                print("  Box too small, try again.")
                continue

            # crop from original
            crop_bgr = self.img_bgr[y:y+rh, x:x+rw]
            crop_pil = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))

            lid = self._pick_landmark(landmarks)
            if lid is None:
                print("  Skipped.")
                continue

            self.crops.append((lid, crop_pil))
            print(f"  Saved crop for: {lid}")

        return self.crops


# ── main ──────────────────────────────────────────────────────────────────────
def main(image_path: Path, n: int):
    landmarks = load_landmarks()

    selector = CropSelector(image_path)
    crops    = selector.run(landmarks)

    if not crops:
        print("\nNo crops collected. Exiting.")
        sys.exit(0)

    print(f"\n🔄 Generating {n} augmented images per crop…\n")
    for lid, pil_img in crops:
        generate_augmented(pil_img, lid, n)

    print(f"\n✅ Done. {len(crops)} landmark(s) processed.")
    print("\nNext steps:")
    print("  python collect_data.py")
    print("  python train.py\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crop landmarks from one image and generate augmented training data."
    )
    parser.add_argument("--image", type=Path, required=True,
                        help="Path to your source image")
    parser.add_argument("--n", type=int, default=60,
                        help="Augmented images to generate per crop (default 60)")
    args = parser.parse_args()
    main(args.image, args.n)
