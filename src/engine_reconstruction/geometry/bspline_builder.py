"""Stage 8 — fit a B-spline surface to a structured grid.

Uses :class:`GeomAPI_PointsToBSplineSurface` to approximate each ``(nu, nv, 3)``
grid as a ``Geom_BSplineSurface`` within ``config.bspline_tol``.

Two safeguards make fitting robust across very different surfaces (clean engine
walls vs. thin pylon strips and capped pylon panels):

* **Continuity + degree fallback**: the primary attempt is C2 at the configured
  degree range; if a fit is invalid or *overshoots*, it falls back to lower
  continuity and lower degree (down to bilinear), which cannot oscillate.
* **Overshoot guard**: high-degree least-squares approximation can balloon far
  outside the point cloud (observed: a thin pylon strip spiking ~11 km). Each
  candidate surface is rejected if any of its control *poles* leaves the grid's
  bounding box by more than a fraction of its diagonal (the convex-hull property
  catches sharp inter-sample spikes that point sampling would miss).

The fitted surface's area is also compared to the grid's triangulated area as a
fidelity signal.
"""

# pythonocc-core stubs under-specify the TColgp_Array2OfPnt 4-arg constructor.
# mypy: disable-error-code="call-arg"
from __future__ import annotations

import numpy as np

from ..grid.grid_statistics import surface_area as grid_surface_area
from ..infrastructure.config import Config
from ..infrastructure.data_types import StructuredGrid, SurfaceFitResult
from ..infrastructure.exceptions import SurfaceFittingError
from ..infrastructure.logging import get_logger
from . import occ_utils

logger = get_logger(__name__)


def _to_array2(grid: StructuredGrid):
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TColgp import TColgp_Array2OfPnt

    pts = grid.points
    nu, nv = grid.nu, grid.nv
    arr = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i in range(nu):
        row = pts[i]
        for j in range(nv):
            x, y, z = row[j]
            arr.SetValue(i + 1, j + 1, gp_Pnt(float(x), float(y), float(z)))
    return arr


def _overshoot(surface, lo: np.ndarray, hi: np.ndarray) -> float:
    """Max distance (m) any control pole lies outside the grid bbox.

    A B-spline surface lies within the convex hull of its control poles, so
    checking the poles reliably detects ballooning that point-sampling can miss
    (high-degree oscillation can spike sharply *between* samples).
    """
    worst = 0.0
    for i in range(1, surface.NbUPoles() + 1):
        for j in range(1, surface.NbVPoles() + 1):
            p = surface.Pole(i, j)
            xyz = np.array([p.X(), p.Y(), p.Z()])
            over = np.maximum.reduce([lo - xyz, xyz - hi, np.zeros(3)])
            worst = max(worst, float(over.max()))
    return worst


def fit_surface(grid: StructuredGrid, config: Config) -> SurfaceFitResult:
    """Fit a B-spline surface to a grid with overshoot guard and degree fallback.

    Args:
        grid: Canonical structured grid.
        config: Run configuration (tolerances, degree bounds).

    Returns:
        A :class:`SurfaceFitResult` (``passed`` reflects the area-deviation gate).

    Raises:
        SurfaceFittingError: If no attempt yields a valid, non-overshooting surface.
    """
    occ_utils.require_occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.GeomAbs import GeomAbs_C0, GeomAbs_C1, GeomAbs_C2
    from OCC.Core.GeomAPI import GeomAPI_PointsToBSplineSurface

    arr = _to_array2(grid)
    lo, hi = grid.bounding_box()
    diag = float(np.linalg.norm(hi - lo))
    overshoot_tol = max(0.25 * diag, 1e-3)
    grid_area = grid_surface_area(grid.points)

    dmin, dmax = config.bspline_degree_min, config.bspline_degree_max
    # (label, continuity, degree_min, degree_max) — primary first, then safer fits.
    attempts = (
        ("C2", GeomAbs_C2, dmin, dmax),
        ("C1", GeomAbs_C1, dmin, min(dmax, 3)),
        ("C0", GeomAbs_C0, 1, 3),
        ("C0", GeomAbs_C0, 1, 1),
    )

    last_err: Exception | None = None
    for cont_name, cont, deg_lo, deg_hi in attempts:
        try:
            builder = GeomAPI_PointsToBSplineSurface(arr, deg_lo, deg_hi, cont, config.bspline_tol)
            if not builder.IsDone():
                continue
            surface = builder.Surface()
            over = _overshoot(surface, lo, hi)
            if over > overshoot_tol:
                logger.info(
                    "Fit %s overshoot %.3gm > %.3gm at %s(deg<=%d); falling back",
                    grid.name,
                    over,
                    overshoot_tol,
                    cont_name,
                    deg_hi,
                )
                continue

            mk = BRepBuilderAPI_MakeFace(surface, config.face_tol)
            if mk.IsDone() and grid_area > 0:
                dev_pct = abs(occ_utils.surface_area(mk.Face()) - grid_area) / grid_area * 100.0
            else:
                dev_pct = 0.0

            level = (
                "OK"
                if dev_pct <= config.area_deviation_pass_pct
                else "WARN" if dev_pct <= config.area_deviation_fail_pct else "FAIL"
            )
            logger.debug(
                "Fit %s: deg=(%d,%d) cont=%s area_dev=%.3f%% overshoot=%.3gm [%s]",
                grid.name,
                surface.UDegree(),
                surface.VDegree(),
                cont_name,
                dev_pct,
                over,
                level,
            )
            return SurfaceFitResult(
                name=grid.name,
                surface=surface,
                degree_u=surface.UDegree(),
                degree_v=surface.VDegree(),
                continuity=cont_name,
                area_deviation_pct=dev_pct,
                passed=dev_pct <= config.area_deviation_fail_pct,
            )
        except Exception as exc:  # try next attempt
            last_err = exc
            logger.debug("Fit %s at %s failed: %s", grid.name, cont_name, exc)

    raise SurfaceFittingError(
        f"Could not fit a stable B-spline surface for {grid.name} "
        f"(all attempts overshot or failed): {last_err}"
    )
