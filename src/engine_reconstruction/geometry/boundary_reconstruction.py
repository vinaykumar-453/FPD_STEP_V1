"""Stage 6 — extract structured boundary curves from grids.

Provides the four boundary polylines (B0-B3) for each grid as
:class:`BoundaryCurve` objects, and a helper to approximate a boundary as a
``Geom_BSplineCurve`` (used for diagnostics and, when needed, explicit shared
edge construction).
"""

from __future__ import annotations

from ..infrastructure.data_types import BoundaryCurve, BoundaryLabel, StructuredGrid
from . import occ_utils

_ALL_LABELS = (BoundaryLabel.B0, BoundaryLabel.B1, BoundaryLabel.B2, BoundaryLabel.B3)


def extract_boundaries(grid: StructuredGrid) -> list[BoundaryCurve]:
    """Return the four boundary curves of a grid."""
    return [BoundaryCurve(grid.name, label, grid.boundary(label)) for label in _ALL_LABELS]


def boundary_to_bspline(curve: BoundaryCurve, tol: float = 1e-4):
    """Approximate a boundary polyline as a ``Geom_BSplineCurve``."""
    occ_utils.require_occ()
    from OCC.Core.GeomAPI import GeomAPI_PointsToBSpline
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TColgp import TColgp_Array1OfPnt

    pts = curve.points
    arr = TColgp_Array1OfPnt(1, pts.shape[0])
    for i in range(pts.shape[0]):
        x, y, z = pts[i]
        arr.SetValue(i + 1, gp_Pnt(float(x), float(y), float(z)))
    return GeomAPI_PointsToBSpline(arr).Curve()
