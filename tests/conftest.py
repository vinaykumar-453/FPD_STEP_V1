"""Shared pytest fixtures and synthetic data helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Make the src/ layout importable without installation.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from engine_reconstruction.infrastructure.data_types import StructuredGrid  # noqa: E402


def cylinder_grid(
    nu: int = 20,
    nv: int = 30,
    radius: float = 1.0,
    length: float = 2.0,
    theta0: float = 0.0,
    theta1: float = np.pi,
) -> np.ndarray:
    """Return a ``(nu, nv, 3)`` half-cylinder grid (axis = x)."""
    x = np.linspace(0.0, length, nu)
    theta = np.linspace(theta0, theta1, nv)
    xx, tt = np.meshgrid(x, theta, indexing="ij")
    pts = np.empty((nu, nv, 3))
    pts[..., 0] = xx
    pts[..., 1] = radius * np.cos(tt)
    pts[..., 2] = radius * np.sin(tt)
    return pts


@pytest.fixture
def grid_inboard() -> StructuredGrid:
    return StructuredGrid("test_inboard", cylinder_grid(theta0=0.0, theta1=np.pi))


@pytest.fixture
def grid_outboard() -> StructuredGrid:
    return StructuredGrid("test_outboard", cylinder_grid(theta0=np.pi, theta1=2 * np.pi))


@pytest.fixture
def icem_file(tmp_path: Path) -> Path:
    """Write a small synthetic ICEM FPD file (i-fastest order) and return its path."""
    ni, nj = 3, 5
    pts = cylinder_grid(ni, nj)
    path = tmp_path / "Synthetic_inboard_free-flying.fpd"
    lines = [f"{ni} {nj}"]
    # i-fastest (column-major): index = i + ni*j
    for j in range(nj):
        for i in range(ni):
            x, y, z = pts[i, j]
            lines.append(f"{x:.12g} {y:.12g} {z:.12g}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def occ_available() -> bool:
    try:
        import OCC  # noqa: F401

        return True
    except ImportError:
        return False


requires_occ = pytest.mark.skipif(not occ_available(), reason="pythonocc-core not installed")
