"""Shared, dependency-light data structures used across all layers.

These dataclasses form the typed contracts between pipeline stages. They depend
only on :mod:`numpy` (never on OpenCASCADE) so the io/grid/topology layers stay
unit-testable without pythonocc-core. OCC B-Rep handles are referenced as
``Any`` in the geometry-stage results to preserve that boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class FpdFormat(str, Enum):
    """Supported FPD point-grid file formats."""

    ICEM = "icem"  # native: line 1 = "ni nj", then ni*nj XYZ rows
    TECPLOT_POINT = "tecplot_point"
    TECPLOT_BLOCK = "tecplot_block"
    PLOT3D = "plot3d"


class SurfaceClass(str, Enum):
    """High-level classification of an FPD surface."""

    ENGINE_BODY = "engine_body"  # axisymmetric physical engine surface (S01-S13)
    PYLON = "pylon"  # physical pylon surface (excluded from shell)
    CFD_DENSITY = "cfd_density"  # CFD auxiliary density zone (separate compound)
    UNKNOWN = "unknown"


class BoundaryLabel(str, Enum):
    """The four structured-grid boundary curves.

    For aerodynamic surfaces (see the RB3135 topology map):
      * B0 = G[0, :]  forward axial / inner radial station
      * B1 = G[-1, :] aft axial / outer radial station
      * B2 = G[:, 0]  circumferential seam at v=0
      * B3 = G[:, -1] circumferential seam at v=N-1
    """

    B0 = "B0"
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"


@dataclass(frozen=True)
class FpdFile:
    """A discovered FPD file with name-derived classification metadata."""

    path: Path
    stem: str
    surface_class: SurfaceClass
    component: str  # e.g. "Spinner", "BP Inner", "Whole Engine Density"
    system: str  # e.g. "Intake", "Bypass", "Core", "CFD Auxiliary"
    role: str  # e.g. "inboard", "outboard", "surface", "base_upstream"


@dataclass
class ParsedFpd:
    """Raw decode of an FPD file before canonical grid orientation is chosen.

    Holds the header dimensions and the points in *file order* (a flat
    ``(n, 3)`` array). The orientation stage turns this into a
    :class:`StructuredGrid` by selecting the correct reshape.
    """

    name: str
    coords: np.ndarray  # (ni*nj, 3) in file order
    ni: int
    nj: int
    source: Path
    source_format: FpdFormat

    @property
    def n_points(self) -> int:
        return int(self.coords.shape[0])


@dataclass
class StructuredGrid:
    """A canonical structured surface point grid of shape ``(nu, nv, 3)``."""

    name: str
    points: np.ndarray  # shape (nu, nv, 3), float64
    source: Path | None = None
    source_format: FpdFormat | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.points.ndim != 3 or self.points.shape[2] != 3:
            raise ValueError(
                f"StructuredGrid '{self.name}' expects (nu, nv, 3); got {self.points.shape}"
            )

    @property
    def nu(self) -> int:
        return int(self.points.shape[0])

    @property
    def nv(self) -> int:
        return int(self.points.shape[1])

    @property
    def n_points(self) -> int:
        return self.nu * self.nv

    def boundary(self, label: BoundaryLabel) -> np.ndarray:
        """Return the ``(M, 3)`` polyline for a boundary curve."""
        if label is BoundaryLabel.B0:
            return self.points[0, :, :]
        if label is BoundaryLabel.B1:
            return self.points[-1, :, :]
        if label is BoundaryLabel.B2:
            return self.points[:, 0, :]
        return self.points[:, -1, :]

    def bounding_box(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(min_xyz, max_xyz)`` over all points."""
        flat = self.points.reshape(-1, 3)
        return flat.min(axis=0), flat.max(axis=0)


@dataclass
class GridValidationReport:
    """Outcome of validating a single structured grid."""

    name: str
    passed: bool
    nu: int
    nv: int
    n_points: int
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)


@dataclass
class BoundaryCurve:
    """A named boundary polyline extracted from a grid."""

    surface: str
    label: BoundaryLabel
    points: np.ndarray  # (M, 3)


@dataclass
class SeamMatch:
    """A detected coincidence between two boundary curves."""

    surface_a: str
    boundary_a: BoundaryLabel
    surface_b: str
    boundary_b: BoundaryLabel
    rms: float
    hausdorff: float
    reversed_match: bool


@dataclass
class SurfaceFitResult:
    """Result of fitting a B-spline surface to a grid (OCC handle as Any)."""

    name: str
    surface: Any  # Geom_BSplineSurface
    degree_u: int
    degree_v: int
    continuity: str  # "C2" | "C1" | "C0"
    area_deviation_pct: float
    passed: bool


@dataclass
class FaceRecord:
    """A constructed/healed CAD face (OCC handle as Any)."""

    name: str
    face: Any  # TopoDS_Face
    valid: bool
    fixed: bool
    grid_name: str


@dataclass
class ComponentRecord:
    """A reconstructed engine component (one or more faces + its shell)."""

    component: str  # e.g. "Spinner"
    system: str  # e.g. "Intake"
    faces: list[FaceRecord]
    shell: Any = None  # TopoDS_Shell
    shell_face_count: int = 0


@dataclass
class WatertightReport:
    """Result of the hard manifold/watertight validation of the merged shell."""

    passed: bool
    n_faces: int
    n_edges: int
    n_shared_edges: int
    n_free_edges: int
    expected_seams_total: int
    expected_seams_shared: int
    unexpected_free_edges: list[dict[str, Any]] = field(default_factory=list)
    missing_seams: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
