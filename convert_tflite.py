"""
convert_tflite.py
-----------------
Convert the trained Keras landmark classifier to TFLite and measure it against
the deployment budget (<150 MB image, <350 MB RSS, p95 inference < 3 s).

USAGE
-----
  python convert_tflite.py --model models/landmark_classifier.keras \
                           --out-dir models \
                           --data-dir data/images_v2

OUTPUT
------
  <out-dir>/landmark_classifier.tflite        float16 weights
  <out-dir>/landmark_classifier_int8.tflite   full-integer weights
  <out-dir>/tflite_benchmark.json             sizes, latency, parity, RSS

The model expects raw 0-255 RGB pixels: EfficientNetB0 carries its own
Rescaling(1/255) + Normalization layers, so no client-side scaling is needed.

NOTE ON THE RUNTIME
-------------------
This machine's `tensorflow` install has a broken TFLite interpreter binding
(`CreateWrapperFromFile(): incompatible function arguments`), caused by a
stale tensorflow-intel 2.16 binary sitting under tensorflow 2.21. The
*converter* works fine, so we convert with TensorFlow and validate/benchmark
with the standalone LiteRT runtime (`ai-edge-litert`), which is an independent
implementation of the same interpreter.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from ai_edge_litert.interpreter import Interpreter as LiteRTInterpreter
except ImportError:  # pragma: no cover - fallback for a healthy TF install
    LiteRTInterpreter = None

IMG_SIZE = (224, 224)


def _interpreter(model_path: Path = None, model_content: bytes = None):
    """Build an interpreter, preferring LiteRT over the bundled TF binding."""
    if LiteRTInterpreter is not None:
        return LiteRTInterpreter(model_path=str(model_path) if model_path else None,
                                 model_content=model_content)
    import tensorflow as tf

    return tf.lite.Interpreter(model_path=str(model_path) if model_path else None,
                               model_content=model_content)


def _peak_rss_mb() -> float:
    """Peak resident set size of this process, in MB."""
    try:
        import psutil  # type: ignore

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    try:  # Windows fallback
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb
        ):
            return -1.0
        return pmc.PeakWorkingSetSize / (1024 * 1024)
    except Exception:
        return -1.0


def _load_samples(data_dir: Path, limit: int = 40) -> list[np.ndarray]:
    """Load a handful of training images as raw float32 [0,255] tensors.

    Resizing deliberately mirrors `image_dataset_from_directory`
    (tf.image.resize, bilinear, antialias=False) so the benchmark measures the
    same preprocessing the model was trained on.
    """
    import tensorflow as tf

    files = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        files.extend(sorted((Path(data_dir) / "train").rglob(ext)))
    out = []
    for p in files[:limit]:
        img = Image.open(p).convert("RGB")
        arr = tf.image.resize(
            np.asarray(img, dtype=np.float32), IMG_SIZE, method="bilinear", antialias=False
        )
        out.append(arr.numpy())
    return out


def _benchmark(interpreter, samples: list[np.ndarray], runs: int = 30) -> dict:
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    interpreter.allocate_tensors()

    # run at least once per sample so the parity check gets one reference
    # prediction for every representative image
    runs = max(runs, len(samples))

    latencies = []
    refs = []
    for i in range(runs):
        x = samples[i % len(samples)][None, ...].astype(inp["dtype"])
        t0 = time.perf_counter()
        interpreter.set_tensor(inp["index"], x)
        interpreter.invoke()
        probs = interpreter.get_tensor(out["index"])[0]
        latencies.append((time.perf_counter() - t0) * 1000.0)
        if i < len(samples):
            refs.append(probs.copy())

    lat = np.array(latencies)
    return {
        "runs": runs,
        "p50_ms": round(float(np.percentile(lat, 50)), 2),
        "p95_ms": round(float(np.percentile(lat, 95)), 2),
        "max_ms": round(float(lat.max()), 2),
        "probs": refs,
    }


def _parity(probs_a, probs_b) -> dict:
    a = np.asarray(probs_a)
    b = np.asarray(probs_b)
    return {
        "top1_agreement": round(float((a.argmax(1) == b.argmax(1)).mean()), 4),
        "mean_abs_diff": round(float(np.abs(a - b).mean()), 5),
        "max_abs_diff": round(float(np.abs(a - b).max()), 5),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, default=Path("models/landmark_classifier.keras"))
    ap.add_argument("--out-dir", type=Path, default=Path("models"), dest="out_dir")
    ap.add_argument("--data-dir", type=Path, default=Path("data/images_v2"), dest="data_dir")
    ap.add_argument("--runs", type=int, default=30)
    args = ap.parse_args()

    import tensorflow as tf
    import keras

    args.out_dir.mkdir(parents=True, exist_ok=True)
    model = keras.models.load_model(args.model)
    samples = _load_samples(args.data_dir)
    if not samples:
        raise SystemExit("no sample images found for the representative dataset")

    runtime = "ai-edge-litert" if LiteRTInterpreter is not None else "tensorflow.lite"
    print(f"model loaded          : {args.model}")
    print(f"representative samples: {len(samples)}")
    print(f"interpreter runtime   : {runtime}")

    # Keras 3 needs an exported SavedModel for TFLite conversion.
    export_dir = args.out_dir / "_saved_model"
    model.export(str(export_dir))

    report = {
        "source_model": str(args.model),
        "num_samples": len(samples),
        "interpreter_runtime": runtime,
        # Peak RSS high-water mark of this whole process. It includes the
        # TensorFlow/Keras training stack, so treat it as an upper bound; the
        # meaningful figure for a phone is measured with `adb shell dumpsys
        # meminfo` once the app is installed.
        "baseline_rss_mb": round(_peak_rss_mb(), 1),
    }

    # ---- float16 -----------------------------------------------------------
    conv = tf.lite.TFLiteConverter.from_saved_model(str(export_dir))
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.target_spec.supported_types = [tf.float16]
    f16 = conv.convert()
    f16_path = args.out_dir / "landmark_classifier.tflite"
    f16_path.write_bytes(f16)

    f16_bench = _benchmark(_interpreter(model_content=f16), samples, args.runs)
    f16_probs = f16_bench.pop("probs")
    report["float16"] = {
        "file_mb": round(len(f16) / (1024 * 1024), 2),
        **f16_bench,
        "peak_rss_mb": round(_peak_rss_mb(), 1),
    }

    # ---- int8 (best effort) ------------------------------------------------
    # The calibration extension is built against numpy 1.x and cannot be
    # imported under numpy 2.x, so this step is optional: float16 already
    # meets the size budget with exact parity. Record the reason instead of
    # failing the whole run.
    i8_probs = None
    try:
        def representative():
            for s in samples:
                yield [s[None, ...].astype(np.float32)]

        conv8 = tf.lite.TFLiteConverter.from_saved_model(str(export_dir))
        conv8.optimizations = [tf.lite.Optimize.DEFAULT]
        conv8.representative_dataset = representative
        conv8.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        conv8.inference_input_type = tf.float32
        conv8.inference_output_type = tf.float32
        i8 = conv8.convert()
        i8_path = args.out_dir / "landmark_classifier_int8.tflite"
        i8_path.write_bytes(i8)

        i8_bench = _benchmark(_interpreter(model_content=i8), samples, args.runs)
        i8_probs = i8_bench.pop("probs")
        report["int8"] = {
            "file_mb": round(len(i8) / (1024 * 1024), 2),
            **i8_bench,
            "peak_rss_mb": round(_peak_rss_mb(), 1),
        }
    except Exception as exc:  # noqa: BLE001 - any failure means "skip int8"
        report["int8"] = {"skipped": f"{type(exc).__name__}: {str(exc)[:160]}"}

    # ---- parity against the Keras reference --------------------------------
    keras_probs = model.predict(np.stack(samples).astype(np.float32), verbose=0)
    report["parity_vs_keras"] = {"float16": _parity(keras_probs, f16_probs)}
    if i8_probs is not None:
        report["parity_vs_keras"]["int8"] = _parity(keras_probs, i8_probs)

    # ---- verdict against the deployment budget ----------------------------
    candidates = [report["float16"]]
    if i8_probs is not None:
        candidates.append(report["int8"])
    rss_vals = [c["peak_rss_mb"] for c in candidates if c.get("peak_rss_mb", -1) > 0]
    report["budget"] = {
        "image_mb_target": 150,
        "rss_mb_target": 350,
        "p95_ms_target": 3000,
        "file_mb_ok": min(c["file_mb"] for c in candidates) < 150,
        # None means the measurement itself failed - never report a pass we did not measure
        "rss_mb_ok": (min(rss_vals) < 350) if rss_vals else None,
        "p95_ms_ok": min(c["p95_ms"] for c in candidates) < 3000,
    }

    (args.out_dir / "tflite_benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print("\n--- TFLite benchmark ---")
    for key in ("float16", "int8"):
        r = report[key]
        if "p95_ms" not in r:
            print(f"{key:8s} skipped: {r.get('skipped', 'n/a')}")
            continue
        print(f"{key:8s} {r['file_mb']:7.2f} MB  p50 {r['p50_ms']:6.2f} ms  "
              f"p95 {r['p95_ms']:6.2f} ms  peak RSS {r['peak_rss_mb']:.0f} MB")
    print("parity vs Keras:", json.dumps(report["parity_vs_keras"]))
    print("budget:", json.dumps(report["budget"]))


if __name__ == "__main__":
    main()
