"""Diagnostic report writers (no GUI).

Serialises stage reports to JSON and a human-readable text summary under the
run's reports directory, for dissertation evidence and debugging.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


def _to_serialisable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_serialisable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _to_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serialisable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def write_json(report: Any, path: Path) -> None:
    """Write any dataclass/dict report to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_serialisable(report), indent=2), encoding="utf-8")
    logger.debug("Wrote diagnostic report: %s", path)


def write_summary(lines: list[str], path: Path) -> None:
    """Write a plain-text run summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote run summary: %s", path)
