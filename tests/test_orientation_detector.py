"""Tests for canonical grid-orientation recovery."""

from __future__ import annotations

import numpy as np

from conftest import cylinder_grid
from engine_reconstruction.infrastructure.data_types import FpdFormat, ParsedFpd
from engine_reconstruction.io import fpd_parser
from engine_reconstruction.topology import orientation_detector


def _parsed_from_grid(pts: np.ndarray, order: str) -> ParsedFpd:
    ni, nj = pts.shape[0], pts.shape[1]
    if order == "i_fastest":
        coords = np.stack([pts[i, j] for j in range(nj) for i in range(ni)])
    else:
        coords = np.stack([pts[i, j] for i in range(ni) for j in range(nj)])
    return ParsedFpd("t", coords, ni, nj, source=None, source_format=FpdFormat.ICEM)  # type: ignore[arg-type]


def test_recovers_i_fastest():
    pts = cylinder_grid(8, 12)
    parsed = _parsed_from_grid(pts, "i_fastest")
    grid = orientation_detector.recover_orientation(parsed)
    assert grid.points.shape == (8, 12, 3)
    np.testing.assert_allclose(grid.points, pts, atol=1e-9)


def test_recovers_j_fastest():
    pts = cylinder_grid(8, 12)
    parsed = _parsed_from_grid(pts, "j_fastest")
    grid = orientation_detector.recover_orientation(parsed)
    np.testing.assert_allclose(grid.points, pts, atol=1e-9)


def test_roundtrip_through_icem_file(icem_file):
    parsed = fpd_parser.parse_fpd(icem_file)
    grid = orientation_detector.recover_orientation(parsed)
    assert grid.points.shape == (3, 5, 3)
    assert grid.meta["orientation"] == "i_fastest"
