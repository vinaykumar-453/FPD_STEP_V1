"""Stage 3 — recover the canonical grid orientation from a raw decode.

The ICEM FPD writer stores points in *column-major* (i-fastest) order, but this
cannot be assumed blindly: choosing the wrong fastest axis scrambles the grid
and produces twisted B-spline surfaces with spikes. We therefore build both
candidate reshapes and pick the one that forms the smoothest structured grid
(minimum total polyline length — the "minimise ring scatter" heuristic).

This module turns a :class:`ParsedFpd` into a canonical
:class:`StructuredGrid` of shape ``(ni, nj, 3)``.
"""

from __future__ import annotations

import numpy as np

from ..infrastructure.data_types import ParsedFpd, StructuredGrid
from ..infrastructure.exceptions import OrientationError
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


def _candidate_i_fastest(coords: np.ndarray, ni: int, nj: int) -> np.ndarray:
    """grid[i, j] = coords[i + ni*j] (column-major / Fortran order)."""
    return coords.reshape(nj, ni, 3).transpose(1, 0, 2)


def _candidate_j_fastest(coords: np.ndarray, ni: int, nj: int) -> np.ndarray:
    """grid[i, j] = coords[i*nj + j] (row-major / C order)."""
    return coords.reshape(ni, nj, 3)


def _roughness(points: np.ndarray) -> float:
    """Total polyline length along both grid directions.

    The correctly-ordered grid threads neighbouring samples, giving the shortest
    total path; a scrambled ordering jumps across the surface and is longer.
    """
    du = np.linalg.norm(np.diff(points, axis=0), axis=2).sum()
    dv = np.linalg.norm(np.diff(points, axis=1), axis=2).sum()
    return float(du + dv)


def recover_orientation(parsed: ParsedFpd) -> StructuredGrid:
    """Select the correct reshape and return a canonical :class:`StructuredGrid`.

    Args:
        parsed: Raw decoded FPD (points in file order).

    Returns:
        Canonical grid of shape ``(ni, nj, 3)``.

    Raises:
        OrientationError: If neither candidate reshape is valid.
    """
    coords, ni, nj = parsed.coords, parsed.ni, parsed.nj
    if coords.shape[0] != ni * nj:
        raise OrientationError(f"{parsed.name}: {coords.shape[0]} points != ni*nj={ni * nj}")

    cand_i = _candidate_i_fastest(coords, ni, nj)
    cand_j = _candidate_j_fastest(coords, ni, nj)
    rough_i = _roughness(cand_i)
    rough_j = _roughness(cand_j)

    if rough_i <= rough_j:
        chosen, order = cand_i, "i_fastest"
    else:
        chosen, order = cand_j, "j_fastest"

    ratio = max(rough_i, rough_j) / max(min(rough_i, rough_j), 1e-30)
    logger.debug(
        "Orientation %s: %s (rough_i=%.3f, rough_j=%.3f, ratio=%.2f)",
        parsed.name,
        order,
        rough_i,
        rough_j,
        ratio,
    )

    return StructuredGrid(
        name=parsed.name,
        points=np.ascontiguousarray(chosen, dtype=np.float64),
        source=parsed.source,
        source_format=parsed.source_format,
        meta={"orientation": order, "roughness_ratio": ratio, "header_ni": ni, "header_nj": nj},
    )
