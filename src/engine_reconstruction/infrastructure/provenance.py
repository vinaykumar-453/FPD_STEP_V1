"""Run provenance capture.

Records the who/what/when of a pipeline run so every output STEP and report is
traceable — a dissertation reproducibility requirement.
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import __version__


def _safe_version(module_name: str) -> str:
    try:
        mod = __import__(module_name)
        return getattr(mod, "__version__", "unknown")
    except Exception:
        return "not-installed"


@dataclass
class Provenance:
    """Immutable-ish snapshot of the run environment and configuration."""

    framework_version: str = __version__
    started_utc: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    python_version: str = sys.version.split()[0]
    platform: str = platform.platform()
    numpy_version: str = field(default_factory=lambda: _safe_version("numpy"))
    scipy_version: str = field(default_factory=lambda: _safe_version("scipy"))
    occ_available: bool = False
    occ_version: str = "unknown"
    config: dict[str, Any] = field(default_factory=dict)
    stages: list[dict[str, Any]] = field(default_factory=list)
    finished_utc: str | None = None
    outcome: str | None = None

    def record_stage(self, name: str, status: str, seconds: float, **extra: Any) -> None:
        """Append a stage timing/status entry."""
        entry: dict[str, Any] = {"stage": name, "status": status, "seconds": round(seconds, 3)}
        entry.update(extra)
        self.stages.append(entry)

    def finalize(self, outcome: str) -> None:
        self.finished_utc = datetime.now(UTC).isoformat()
        self.outcome = outcome

    def to_json(self) -> str:
        def _default(obj: Any) -> str:
            return str(obj)

        return json.dumps(asdict(self), indent=2, default=_default)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")


def detect_occ() -> tuple[bool, str]:
    """Return ``(available, version)`` for pythonocc-core."""
    try:
        import OCC  # noqa: F401
        from OCC.Core import VERSION  # type: ignore

        return True, str(VERSION)
    except Exception:
        try:
            import OCC  # noqa: F401

            return True, "unknown"
        except Exception:
            return False, "not-installed"
