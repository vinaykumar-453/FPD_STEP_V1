"""Structured logging configuration.

Provides a single :func:`get_logger` entry point and :func:`configure_logging`
to set up console + optional file handlers. No global mutable state beyond the
standard library's logging registry; configuration is idempotent.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_ROOT_NAME = "engine_reconstruction"
_configured = False


def configure_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> None:
    """Configure the package root logger.

    Args:
        level: Logging level for the package root logger.
        log_file: Optional path to also write logs to a file.

    Idempotent: repeated calls reset handlers rather than duplicating them.
    """
    global _configured
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(level)
    root.handlers.clear()
    root.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(level)
    root.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the package root.

    Args:
        name: Dotted module name, typically ``__name__``.

    Returns:
        A configured :class:`logging.Logger`.
    """
    if not _configured:
        configure_logging()
    short = name.split("engine_reconstruction.", 1)[-1]
    return logging.getLogger(f"{_ROOT_NAME}.{short}")
