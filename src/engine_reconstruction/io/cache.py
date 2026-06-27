"""On-disk cache for oriented structured grids.

Parsing + orientation of the largest grids (~40 MB ASCII) is the slowest I/O in
the pipeline. This cache stores canonical grids as compressed ``.npz`` keyed by
source path and modification time, so reruns skip re-parsing unchanged files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from ..infrastructure.data_types import FpdFormat, StructuredGrid
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


class GridCache:
    """Compressed ``.npz`` cache of :class:`StructuredGrid` objects."""

    def __init__(self, cache_dir: Path, enabled: bool = True) -> None:
        self.cache_dir = cache_dir
        self.enabled = enabled
        if enabled:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, source: Path) -> Path:
        stat = source.stat()
        digest = hashlib.sha1(
            f"{source.resolve()}::{stat.st_mtime_ns}::{stat.st_size}".encode()
        ).hexdigest()[:16]
        return self.cache_dir / f"{source.stem}.{digest}.npz"

    def load(self, source: Path, name: str) -> StructuredGrid | None:
        """Return a cached grid for ``source`` or ``None`` on miss."""
        if not self.enabled:
            return None
        key = self._key(source)
        if not key.exists():
            return None
        try:
            with np.load(key, allow_pickle=False) as data:
                fmt_val = str(data["fmt"]) if "fmt" in data else None
                grid = StructuredGrid(
                    name=name,
                    points=data["points"],
                    source=source,
                    source_format=FpdFormat(fmt_val) if fmt_val else None,
                )
            logger.debug("Grid cache hit: %s", source.name)
            return grid
        except Exception as exc:  # pragma: no cover - cache is best-effort
            logger.warning("Grid cache read failed for %s: %s", source.name, exc)
            return None

    def store(self, grid: StructuredGrid) -> None:
        """Persist a grid to the cache (best-effort)."""
        if not self.enabled or grid.source is None:
            return
        key = self._key(grid.source)
        try:
            np.savez_compressed(
                key,
                points=grid.points,
                fmt=(grid.source_format.value if grid.source_format else ""),
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Grid cache write failed for %s: %s", grid.name, exc)
