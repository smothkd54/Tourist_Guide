#!/usr/bin/env python3
"""
preflight_check.py
--------------------
Run this before starting the server in any deployment (Docker
entrypoint, CI smoke test, systemd ExecStartPre). Exits non-zero if
anything required is missing, so a broken deployment fails loudly at
startup instead of silently serving 503s on every /predict call.

USAGE
-----
  python preflight_check.py
  echo $?     # 0 = ready to serve, 1 = missing required files

In Docker, wire this into the entrypoint:
  CMD python preflight_check.py && python backend/app.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT     = Path(__file__).resolve().parent
MODEL_PATH       = PROJECT_ROOT / "models" / "landmark_classifier.keras"
CLASS_NAMES_PATH = PROJECT_ROOT / "models" / "class_names.json"
LANDMARKS_PATH   = PROJECT_ROOT / "data" / "landmarks.json"
FRONTEND_PATH    = PROJECT_ROOT / "frontend" / "index.html"


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "OK " if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def main():
    print("Pre-flight check\n")
    all_ok = True

    all_ok &= check("landmarks.json exists", LANDMARKS_PATH.exists(),
                     f"expected at {LANDMARKS_PATH}")

    if LANDMARKS_PATH.exists():
        try:
            data = json.loads(LANDMARKS_PATH.read_text())
            n = len(data.get("landmarks", []))
            all_ok &= check(f"landmarks.json parses, {n} entries", n > 0)
        except Exception as e:
            all_ok &= check("landmarks.json parses", False, str(e))

    model_exists = MODEL_PATH.exists()
    all_ok &= check("trained model exists", model_exists,
                     f"expected at {MODEL_PATH} — run train.py")

    classes_exist = CLASS_NAMES_PATH.exists()
    all_ok &= check("class_names.json exists", classes_exist,
                     f"expected at {CLASS_NAMES_PATH}")

    if model_exists and classes_exist:
        try:
            class_names = json.loads(CLASS_NAMES_PATH.read_text())
            all_ok &= check(f"class_names.json parses, {len(class_names)} classes",
                            len(class_names) > 0)
        except Exception as e:
            all_ok &= check("class_names.json parses", False, str(e))

    all_ok &= check("frontend/index.html exists", FRONTEND_PATH.exists())

    print()
    if all_ok:
        print("All checks passed. Safe to start the server.")
        sys.exit(0)
    else:
        print("One or more checks failed. Fix the above before deploying.")
        print("The server would otherwise start but serve broken responses.")
        sys.exit(1)


if __name__ == "__main__":
    main()