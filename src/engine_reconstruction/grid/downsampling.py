"""Optional structured-grid downsampling.

Off by default (full-resolution fitting). When enabled it strides each grid
direction so neither dimension exceeds ``config.max_points_per_dir`` while always
retaining the four boundary rows/columns (so seams remain exact).
"""

from __future__ import annotations

import numpy as np

from ..infrastructure.config import Config
from ..infrastructure.data_types import StructuredGrid
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


def _stride_indices(n: int, max_n: int) -> np.ndarray:
    """Return indices that include endpoints and stride the interior."""
    if n <= max_n:
        return np.arange(n)
    step = int(np.ceil((n - 1) / (max_n - 1)))
    idx = np.arange(0, n, step)
    if idx[-1] != n - 1:
        idx = np.append(idx, n - 1)
    return idx


def downsample_to_cap(grid: StructuredGrid, max_per_dir: int) -> StructuredGrid:
    """Stride a grid so neither dimension exceeds ``max_per_dir`` (always applied).

    Endpoints are always retained so seams stay exact. Used for oversized
    cosmetic surfaces (e.g. the multi-million-point pylon heatshield) that would
    otherwise make full-resolution B-spline fitting intractable.
    """
    iu = _stride_indices(grid.nu, max_per_dir)
    iv = _stride_indices(grid.nv, max_per_dir)
    if iu.size == grid.nu and iv.size == grid.nv:
        return grid
    sub = grid.points[np.ix_(iu, iv, np.arange(3))]
    logger.info(
        "Capped %s from %dx%d to %dx%d for tractable fitting",
        grid.name,
        grid.nu,
        grid.nv,
        iu.size,
        iv.size,
    )
    return StructuredGrid(
        name=grid.name,
        points=np.ascontiguousarray(sub),
        source=grid.source,
        source_format=grid.source_format,
        meta={**grid.meta, "downsampled": True, "cap": max_per_dir},
    )


def downsample(grid: StructuredGrid, config: Config) -> StructuredGrid:
    """Return a downsampled copy of ``grid`` (or the grid itself if not needed)."""
    if not config.downsample:
        return grid
    iu = _stride_indices(grid.nu, config.max_points_per_dir)
    iv = _stride_indices(grid.nv, config.max_points_per_dir)
    if iu.size == grid.nu and iv.size == grid.nv:
        return grid
    sub = grid.points[np.ix_(iu, iv, np.arange(3))]
    logger.info(
        "Downsampled %s from %dx%d to %dx%d",
        grid.name,
        grid.nu,
        grid.nv,
        iu.size,
        iv.size,
    )
    return StructuredGrid(
        name=grid.name,
        points=np.ascontiguousarray(sub),
        source=grid.source,
        source_format=grid.source_format,
        meta={**grid.meta, "downsampled": True},
    )
