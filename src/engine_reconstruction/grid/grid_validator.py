"""Stage 4 — validate a structured grid and reject invalid ones.

Checks dimensions, NaN/Inf, full-collapse degeneracies, and excessive duplicate
points. A degenerate *line* of points (e.g. the spinner nose tip) is a legitimate
structured-grid feature and is reported as a warning, not a failure.
"""

from __future__ import annotations

import numpy as np

from ..infrastructure.config import Config
from ..infrastructure.data_types import GridValidationReport, StructuredGrid
from ..infrastructure.logging import get_logger
from . import grid_statistics

logger = get_logger(__name__)


def validate_grid(grid: StructuredGrid, config: Config) -> GridValidationReport:
    """Validate a single structured grid.

    Args:
        grid: The grid to validate.
        config: Run configuration (tolerances).

    Returns:
        A :class:`GridValidationReport` with ``passed`` set accordingly.
    """
    issues: list[str] = []
    warnings: list[str] = []
    pts = grid.points

    if grid.nu < 2 or grid.nv < 2:
        issues.append(f"degenerate dimensions nu={grid.nu}, nv={grid.nv} (need >=2)")

    if not np.all(np.isfinite(pts)):
        n_bad = int(np.count_nonzero(~np.isfinite(pts)))
        issues.append(f"{n_bad} non-finite coordinate value(s)")

    stats = grid_statistics.compute_statistics(grid, config.duplicate_point_tol)

    if stats["area"] <= 0.0 and not issues:
        issues.append("zero surface area (fully collapsed grid)")

    # Degenerate boundary lines (a whole boundary collapsed to a point) -> warn.
    for label, line in (("B0", pts[0, :, :]), ("B1", pts[-1, :, :])):
        span = float(np.linalg.norm(line.max(axis=0) - line.min(axis=0)))
        if span < config.duplicate_point_tol:
            warnings.append(f"boundary {label} is degenerate (collapsed to a point)")

    dup_frac = stats["duplicate_edges"] / max(1.0, (grid.nu * grid.nv))
    if dup_frac > 0.5:
        issues.append(f"excessive duplicate adjacent points ({dup_frac:.0%} of cells)")
    elif stats["duplicate_edges"] > 0:
        warnings.append(f"{int(stats['duplicate_edges'])} duplicate adjacent point(s)")

    passed = not issues
    report = GridValidationReport(
        name=grid.name,
        passed=passed,
        nu=grid.nu,
        nv=grid.nv,
        n_points=grid.n_points,
        issues=issues,
        warnings=warnings,
        stats=stats,
    )
    if not passed:
        logger.warning("Grid %s FAILED validation: %s", grid.name, "; ".join(issues))
    elif warnings:
        logger.debug("Grid %s passed with warnings: %s", grid.name, "; ".join(warnings))
    return report
