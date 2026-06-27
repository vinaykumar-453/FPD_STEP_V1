"""Stages 5-6 — detect neighbouring surfaces by matching boundary curves.

For every ordered pair of surfaces we compare their four boundary polylines
(B0-B3) and report coincident pairs using a symmetric nearest-neighbour RMS and
Hausdorff distance (computed with a KD-tree). These matches drive both the
adjacency graph and the diagnostic seam report.
"""

from __future__ import annotations

import itertools

import numpy as np
from scipy.spatial import cKDTree

from ..infrastructure.config import Config
from ..infrastructure.data_types import BoundaryLabel, SeamMatch, StructuredGrid
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)

_ALL_LABELS = (BoundaryLabel.B0, BoundaryLabel.B1, BoundaryLabel.B2, BoundaryLabel.B3)


def _polyline_distance(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Return ``(rms, hausdorff)`` between two polylines (symmetric)."""
    ta, tb = cKDTree(a), cKDTree(b)
    da, _ = tb.query(a)  # a -> b
    db, _ = ta.query(b)  # b -> a
    rms = float(np.sqrt((np.mean(da**2) + np.mean(db**2)) / 2.0))
    hausdorff = float(max(da.max(), db.max()))
    return rms, hausdorff


def _is_reversed(a: np.ndarray, b: np.ndarray) -> bool:
    """True if the polylines run in opposite directions (endpoints swapped)."""
    fwd = np.linalg.norm(a[0] - b[0]) + np.linalg.norm(a[-1] - b[-1])
    rev = np.linalg.norm(a[0] - b[-1]) + np.linalg.norm(a[-1] - b[0])
    return rev < fwd


def match_boundaries(
    grid_a: StructuredGrid,
    grid_b: StructuredGrid,
    config: Config,
) -> list[SeamMatch]:
    """Return coincident boundary pairs between two grids within tolerance."""
    matches: list[SeamMatch] = []
    for la in _ALL_LABELS:
        ca = grid_a.boundary(la)
        for lb in _ALL_LABELS:
            cb = grid_b.boundary(lb)
            rms, hd = _polyline_distance(ca, cb)
            if rms <= config.seam_match_rms_tol:
                matches.append(
                    SeamMatch(
                        surface_a=grid_a.name,
                        boundary_a=la,
                        surface_b=grid_b.name,
                        boundary_b=lb,
                        rms=rms,
                        hausdorff=hd,
                        reversed_match=_is_reversed(ca, cb),
                    )
                )
    return matches


def detect_all(
    grids: dict[str, StructuredGrid],
    config: Config,
) -> list[SeamMatch]:
    """Detect all coincident boundary pairs across a set of grids.

    Args:
        grids: Mapping of surface name -> grid.
        config: Run configuration.

    Returns:
        List of :class:`SeamMatch` (each unordered surface pair reported once).
    """
    names = sorted(grids)
    matches: list[SeamMatch] = []
    for name_a, name_b in itertools.combinations(names, 2):
        matches.extend(match_boundaries(grids[name_a], grids[name_b], config))
    logger.info(
        "Detected %d coincident boundary matches across %d surfaces", len(matches), len(names)
    )
    return matches
