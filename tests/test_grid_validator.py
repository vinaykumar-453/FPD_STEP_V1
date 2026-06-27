"""Tests for structured-grid validation and statistics."""

from __future__ import annotations

import numpy as np

from conftest import cylinder_grid
from engine_reconstruction.grid import grid_statistics, grid_validator
from engine_reconstruction.infrastructure.config import Config
from engine_reconstruction.infrastructure.data_types import StructuredGrid


def test_valid_grid_passes():
    grid = StructuredGrid("ok", cylinder_grid(10, 15))
    rep = grid_validator.validate_grid(grid, Config())
    assert rep.passed
    assert rep.stats["area"] > 0


def test_nonfinite_fails():
    pts = cylinder_grid(6, 6)
    pts[2, 2, 0] = np.nan
    rep = grid_validator.validate_grid(StructuredGrid("bad", pts), Config())
    assert not rep.passed
    assert any("non-finite" in i for i in rep.issues)


def test_degenerate_dims_fails():
    pts = np.zeros((1, 5, 3))
    rep = grid_validator.validate_grid(StructuredGrid("deg", pts), Config())
    assert not rep.passed


def test_surface_area_matches_known():
    # Quarter cylinder, r=1, length=2: area = (pi/2) * r * L = pi
    pts = cylinder_grid(40, 60, radius=1.0, length=2.0, theta0=0.0, theta1=np.pi / 2)
    area = grid_statistics.surface_area(pts)
    assert abs(area - np.pi) < 1e-2


def test_boundary_extraction_shapes():
    grid = StructuredGrid("b", cylinder_grid(7, 9))
    from engine_reconstruction.infrastructure.data_types import BoundaryLabel

    assert grid.boundary(BoundaryLabel.B0).shape == (9, 3)
    assert grid.boundary(BoundaryLabel.B2).shape == (7, 3)
