"""
logging_setup.py
----------------
Shared logging configuration for all scripts.

Sets up dual output:
  - Console handler: with emojis, INFO level
  - File handler: clean text (no emojis), UTF-8, RotatingFileHandler (5 MB × 3 backups)

USAGE
-----
  from logging_setup import setup_logging
  logger = setup_logging("my_script")

Environment variables:
  LOG_DIR  — directory for log files (default: logs/)
"""

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # misc symbols, emoticons, etc.
    "\U00002702-\U000027B0"  # dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero width joiner
    "\U00002600-\U000026FF"  # misc symbols
    "]+",
    flags=re.UNICODE,
)

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


class _EmojiStripFormatter(logging.Formatter):
    """Formatter that strips emojis — used for file output only."""

    def format(self, record):
        msg = super().format(record)
        return _EMOJI_RE.sub("", msg)


def setup_logging(name: str, log_dir: str | None = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging for *name* with console + rotating file handlers.

    Idempotent: calling multiple times with the same *name* won't duplicate
    handlers.

    Returns the configured logger.
    """
    logger = logging.getLogger(name)

    # ── idempotent — already configured ──────────────────────────────────
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # ── console handler (stderr, with emojis) ────────────────────────────
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    logger.addHandler(console)

    # ── file handler (rotating, emoji-stripped, UTF-8) ───────────────────
    resolved_dir = Path(os.environ.get("LOG_DIR", log_dir or "logs"))
    resolved_dir.mkdir(parents=True, exist_ok=True)
    log_path = resolved_dir / f"{name}.log"

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(_EmojiStripFormatter(_FORMAT, datefmt=_DATEFMT))
    logger.addHandler(file_handler)

    return logger
