"""Build and persist a surface metadata registry.

Aggregates per-file classification and grid statistics into a single registry
that is written as CSV + JSON for diagnostics and dissertation reporting.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..infrastructure.data_types import FpdFile, StructuredGrid
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SurfaceMetadata:
    """Per-surface metadata row."""

    stem: str
    surface_class: str
    component: str
    system: str
    role: str
    nu: int = 0
    nv: int = 0
    n_points: int = 0
    bbox_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bbox_max: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class MetadataRegistry:
    """Collection of :class:`SurfaceMetadata` rows."""

    rows: list[SurfaceMetadata] = field(default_factory=list)

    def add(self, fpd: FpdFile, grid: StructuredGrid | None) -> None:
        meta = SurfaceMetadata(
            stem=fpd.stem,
            surface_class=fpd.surface_class.value,
            component=fpd.component,
            system=fpd.system,
            role=fpd.role,
        )
        if grid is not None:
            lo, hi = grid.bounding_box()
            meta.nu, meta.nv, meta.n_points = grid.nu, grid.nv, grid.n_points
            meta.bbox_min = tuple(float(v) for v in lo)  # type: ignore[assignment]
            meta.bbox_max = tuple(float(v) for v in hi)  # type: ignore[assignment]
        self.rows.append(meta)

    def write_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "stem",
                    "surface_class",
                    "component",
                    "system",
                    "role",
                    "nu",
                    "nv",
                    "n_points",
                    "xmin",
                    "ymin",
                    "zmin",
                    "xmax",
                    "ymax",
                    "zmax",
                ]
            )
            for r in self.rows:
                writer.writerow(
                    [
                        r.stem,
                        r.surface_class,
                        r.component,
                        r.system,
                        r.role,
                        r.nu,
                        r.nv,
                        r.n_points,
                        *r.bbox_min,
                        *r.bbox_max,
                    ]
                )
        logger.info("Wrote surface metadata CSV: %s (%d rows)", path, len(self.rows))

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: list[dict[str, Any]] = [asdict(r) for r in self.rows]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
