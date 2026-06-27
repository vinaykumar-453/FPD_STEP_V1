"""Stage 4a — compute descriptive statistics for a structured grid.

Pure numpy; no OpenCASCADE. Statistics feed both validation and the metadata
registry, and are cheap enough to run on every grid.
"""

from __future__ import annotations

import numpy as np

from ..infrastructure.data_types import StructuredGrid


def cell_areas(points: np.ndarray) -> np.ndarray:
    """Approximate per-cell area via the two triangles of each quad.

    Args:
        points: ``(nu, nv, 3)`` grid.

    Returns:
        ``(nu-1, nv-1)`` array of quad areas.
    """
    p00 = points[:-1, :-1, :]
    p10 = points[1:, :-1, :]
    p01 = points[:-1, 1:, :]
    p11 = points[1:, 1:, :]
    t1 = 0.5 * np.linalg.norm(np.cross(p10 - p00, p01 - p00), axis=2)
    t2 = 0.5 * np.linalg.norm(np.cross(p10 - p11, p01 - p11), axis=2)
    return t1 + t2


def surface_area(points: np.ndarray) -> float:
    """Total triangulated surface area of the grid."""
    if points.shape[0] < 2 or points.shape[1] < 2:
        return 0.0
    return float(cell_areas(points).sum())


def edge_lengths(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (u-direction, v-direction) edge-length arrays."""
    du = np.linalg.norm(np.diff(points, axis=0), axis=2)
    dv = np.linalg.norm(np.diff(points, axis=1), axis=2)
    return du, dv


def duplicate_point_count(points: np.ndarray, tol: float) -> int:
    """Count adjacent duplicate points (collapsed grid cells) within ``tol``."""
    du, dv = edge_lengths(points)
    return int(np.count_nonzero(du < tol) + np.count_nonzero(dv < tol))


def compute_statistics(grid: StructuredGrid, duplicate_tol: float) -> dict[str, float]:
    """Compute a dictionary of grid statistics.

    Args:
        grid: The structured grid.
        duplicate_tol: Distance below which adjacent points count as duplicates.

    Returns:
        Mapping of statistic name to value.
    """
    pts = grid.points
    du, dv = edge_lengths(pts)
    lo, hi = grid.bounding_box()
    nonzero_du = du[du > 0]
    nonzero_dv = dv[dv > 0]
    return {
        "area": surface_area(pts),
        "min_edge_u": float(nonzero_du.min()) if nonzero_du.size else 0.0,
        "max_edge_u": float(du.max()) if du.size else 0.0,
        "min_edge_v": float(nonzero_dv.min()) if nonzero_dv.size else 0.0,
        "max_edge_v": float(dv.max()) if dv.size else 0.0,
        "bbox_dx": float(hi[0] - lo[0]),
        "bbox_dy": float(hi[1] - lo[1]),
        "bbox_dz": float(hi[2] - lo[2]),
        "duplicate_edges": float(duplicate_point_count(pts, duplicate_tol)),
        "diagonal": float(np.linalg.norm(hi - lo)),
    }
