"""Guards for the committed dataset split manifest.

The training images are not in git, so ``data/images_v2/manifests/split.json``
is the only record of how the 29-class dataset was built. These tests keep it
internally consistent: a source photo may not appear in two splits, every
class in the served model must have training images, and the class order must
match ``models/class_names.json`` (Keras derives labels from directory names,
so a reordering would silently remap every prediction).

``scripts/build_dataset.py`` does the same checks before rebuilding the tree;
running them here means a bad manifest fails CI instead of a later retrain.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _build_dataset_module():
    spec = importlib.util.spec_from_file_location(
        "build_dataset", ROOT / "scripts" / "build_dataset.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _records():
    return json.loads(
        (ROOT / "data" / "images_v2" / "manifests" / "split.json").read_text("utf-8")
    )


def test_manifest_is_consistent():
    module = _build_dataset_module()
    problems = module.check_structure(_records())
    assert problems == [], "split manifest problems:\n" + "\n".join(problems)


def test_no_source_photo_appears_in_two_splits():
    seen = {}
    for record in _records():
        assert record["src"] not in seen, (
            f"{record['src']} is in both {seen[record['src']]} and {record['split']}"
        )
        seen[record["src"]] = record["split"]


def test_every_served_class_has_training_images():
    classes = json.loads((ROOT / "models" / "class_names.json").read_text("utf-8"))
    train = {r["cls"] for r in _records() if r["split"] == "train"}
    assert sorted(classes) == sorted(train)


def test_every_split_has_images():
    counts = {}
    for record in _records():
        counts[record["split"]] = counts.get(record["split"], 0) + 1
    assert counts.get("train", 0) >= 100
    assert counts.get("val", 0) >= 30
    assert counts.get("test", 0) >= 30
