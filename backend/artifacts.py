"""Shared artifact helpers used by the API and the preflight check."""

from pathlib import Path


def is_lfs_pointer(path: Path) -> bool:
    """Return True if *path* is a Git LFS pointer stub, not real content."""
    if path.stat().st_size > 1024:
        return False
    try:
        return path.read_text(encoding="utf-8", errors="ignore").startswith(
            "version https://git-lfs.github.com"
        )
    except OSError:
        return False
