"""
backend/tflite_model.py
-----------------------
Run the landmark classifier through the TFLite runtime instead of Keras.

Why this exists
---------------
Loading TensorFlow/Keras costs ~392 MB of resident memory per process. On a
512 MB free web instance, two gunicorn workers would be killed. The same model
as TFLite needs ~113 MB, which leaves room for two workers plus Flask.

The class deliberately exposes `.predict(batch)`, so the rest of the app (and
the existing tests) do not care which runtime is behind it.

It also carries `resize_bilinear`, a NumPy implementation of
`tf.image.resize(..., method="bilinear", antialias=False)`. That is the resize
used by `image_dataset_from_directory` during training, so serving must match
it — using PIL's LANCZOS instead changed the top-1 answer on 28% of test
images. Keeping it in NumPy means production does not need TensorFlow at all.
"""

import threading

import numpy as np

__all__ = ["TFLiteModel", "resize_bilinear"]


def resize_bilinear(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """NumPy equivalent of tf.image.resize(image, size, method="bilinear").

    Matches TensorFlow's default half-pixel-centre sampling with
    `antialias=False`. Input is HWC, output is HWC float32.
    """
    height, width = size
    src = np.asarray(image, dtype=np.float32)
    in_h, in_w = src.shape[:2]

    scale_y = in_h / height
    scale_x = in_w / width

    # half-pixel centres, clamped to the valid range
    ys = np.clip((np.arange(height) + 0.5) * scale_y - 0.5, 0, in_h - 1)
    xs = np.clip((np.arange(width) + 0.5) * scale_x - 0.5, 0, in_w - 1)

    y0 = np.floor(ys).astype(np.int64)
    x0 = np.floor(xs).astype(np.int64)
    y1 = np.minimum(y0 + 1, in_h - 1)
    x1 = np.minimum(x0 + 1, in_w - 1)

    wy = (ys - y0).reshape(-1, 1, 1)
    wx = (xs - x0).reshape(1, -1, 1)

    top = src[y0][:, x0] * (1 - wx) + src[y0][:, x1] * wx
    bottom = src[y1][:, x0] * (1 - wx) + src[y1][:, x1] * wx
    return (top * (1 - wy) + bottom * wy).astype(np.float32)


class TFLiteModel:
    """Thin wrapper giving a TFLite interpreter a Keras-like `.predict()`."""

    def __init__(self, model_path):
        from ai_edge_litert.interpreter import Interpreter

        self._interpreter = Interpreter(model_path=str(model_path))
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]
        self._output = self._interpreter.get_output_details()[0]
        # One interpreter is not re-entrant; gunicorn threads must not share it
        # mid-invoke.
        self._lock = threading.Lock()

    @property
    def input_shape(self) -> tuple[int, ...]:
        return tuple(self._input["shape"])

    def predict(self, batch, verbose: int = 0):  # noqa: ARG002 - Keras-compatible
        batch = np.asarray(batch, dtype=np.float32)
        if batch.ndim == 3:
            batch = batch[None, ...]

        out = []
        with self._lock:
            for row in batch:
                self._interpreter.set_tensor(
                    self._input["index"], row[None, ...].astype(self._input["dtype"])
                )
                self._interpreter.invoke()
                out.append(self._interpreter.get_tensor(self._output["index"])[0].copy())
        return np.asarray(out, dtype=np.float32)
