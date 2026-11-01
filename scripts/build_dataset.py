"""
scripts/build_dataset.py
------------------------
Rebuild ``data/images_v2`` from the committed split manifest.

Why this exists
---------------
The images themselves are not in git (316 MB), but
``data/images_v2/manifests/split.json`` records, for every training image,
where it came from and which split it belongs to. Without this script the
tree could only be recreated by memory, so a fresh clone could serve the model
but never retrain it.

Sources live in ``data/images/`` (the original dataset) and
``data/images_enriched/`` (Wikimedia Commons downloads). Neither is committed;
restore them from the project archive first.

USAGE
-----
  python scripts/build_dataset.py                  # copy what is missing
  python scripts/build_dataset.py --force          # rebuild every file
  python scripts/build_dataset.py --verify         # report only, change nothing
  python scripts/build_dataset.py --update-manifest  # rewrite stale sha256 values

A stale hash is reported, not fatal: ``src`` -> ``path`` is the authoritative
mapping, and at least one recorded hash was taken before that file was
re-encoded. ``--update-manifest`` makes the manifest describe what is actually
on disk.
"""

import argparse
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "images_v2" / "manifests" / "split.json"
CLASS_NAMES = ROOT / "models" / "class_names.json"
REQUIRED = ("split", "cls", "path", "src", "sha", "origin")
SPLITS = ("train", "val", "test")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_records() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def check_structure(records: list[dict]) -> list[str]:
    """Problems that make the manifest itself untrustworthy."""
    problems = []

    for record in records:
        missing = [key for key in REQUIRED if key not in record]
        if missing:
            problems.append(f"{record.get('path', '?')}: missing {missing}")
            continue
        expected_prefix = f"data/images_v2/{record['split']}/{record['cls']}/"
        if not record["path"].startswith(expected_prefix):
            problems.append(f"{record['path']}: not under {expected_prefix}")
        if record["split"] not in SPLITS:
            problems.append(f"{record['path']}: unknown split {record['split']!r}")

    # One source photo must not appear twice: that would put the same image in
    # two splits (or twice in one), and the reported accuracy would be wrong.
    by_source = defaultdict(list)
    for record in records:
        by_source[record["src"]].append(record["split"])
    for source, splits in sorted(by_source.items()):
        if len(splits) > 1:
            problems.append(f"{source}: used by {len(splits)} records ({sorted(set(splits))})")

    by_path = defaultdict(int)
    for record in records:
        by_path[record["path"]] += 1
    for path, count in sorted(by_path.items()):
        if count > 1:
            problems.append(f"{path}: listed {count} times")

    if CLASS_NAMES.exists():
        classes = json.loads(CLASS_NAMES.read_text(encoding="utf-8"))
        in_data = {record["cls"] for record in records}
        missing = sorted(set(classes) - in_data)
        extra = sorted(in_data - set(classes))
        if missing:
            problems.append(f"classes in class_names.json but not in the split: {missing}")
        if extra:
            problems.append(f"classes in the split but not in class_names.json: {extra}")
        if classes != sorted(classes):
            problems.append("class_names.json is not alphabetical; label order would change")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="copy even if the target exists")
    parser.add_argument("--verify", action="store_true", help="report only, change nothing")
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        dest="update_manifest",
        help="rewrite sha256 values that no longer match the files on disk",
    )
    args = parser.parse_args()

    records = load_records()
    problems = check_structure(records)
    for problem in problems:
        print(f"MANIFEST: {problem}", file=sys.stderr)
    if problems:
        print("Refusing to build from an inconsistent manifest.", file=sys.stderr)
        return 1

    missing_sources = [r["src"] for r in records if not (ROOT / r["src"]).exists()]
    if missing_sources:
        print(f"{len(missing_sources)} source files are missing, e.g.:", file=sys.stderr)
        for source in missing_sources[:10]:
            print(f"  {source}", file=sys.stderr)
        print(
            "Restore data/images/ and data/images_enriched/ from the project "
            "archive, then run this script again.",
            file=sys.stderr,
        )
        return 1

    copied = skipped = mismatched = 0
    stale: list[dict] = []

    for record in records:
        source = ROOT / record["src"]
        target = ROOT / record["path"]

        if args.verify:
            if not target.exists():
                print(f"MISSING {record['path']}", file=sys.stderr)
                mismatched += 1
                continue
        elif target.exists() and not args.force:
            skipped += 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1

        actual = sha256(target)
        if actual != record["sha"]:
            mismatched += 1
            stale.append(record)
            if args.update_manifest:
                record["sha"] = actual
            else:
                print(f"HASH  {record['path']} does not match the manifest", file=sys.stderr)

    if args.update_manifest and stale:
        MANIFEST.write_text(
            json.dumps(records, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"manifest updated: {len(stale)} sha256 value(s) rewritten")

    counts = defaultdict(int)
    for record in records:
        counts[record["split"]] += 1

    print(f"manifest records : {len(records)}")
    print(f"classes          : {len({r['cls'] for r in records})}")
    print("images per split : " + ", ".join(f"{s}={counts[s]}" for s in SPLITS))
    if not args.verify:
        print(f"copied           : {copied}")
        print(f"already present  : {skipped}")
    print(f"hash mismatches  : {mismatched}")

    return 1 if mismatched and not args.update_manifest else 0


if __name__ == "__main__":
    sys.exit(main())
