"""Stage 10 — sew faces into shells.

Uses ``BRepBuilderAPI_Sewing`` over a progressive tolerance ladder. For the
merged engine shell we pick the tolerance that eliminates the most *unsewn
coincident seams* (coincident free-edge pairs) without collapsing distinct
geometry. Non-manifold mode is off and solids are never forced (open aero
boundaries must stay open).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..infrastructure.config import Config
from ..infrastructure.exceptions import ShellAssemblyError
from ..infrastructure.logging import get_logger
from . import occ_utils

logger = get_logger(__name__)


@dataclass
class SewResult:
    """Outcome of a sewing pass."""

    shape: Any
    tolerance: float
    n_faces: int
    n_shells: int
    n_free_edges: int
    n_shared_edges: int
    n_unsewn_pairs: int


def _iter_shells(shape) -> list:
    from OCC.Core.TopAbs import TopAbs_SHELL
    from OCC.Core.TopExp import TopExp_Explorer

    out = []
    exp = TopExp_Explorer(shape, TopAbs_SHELL)
    while exp.More():
        out.append(exp.Current())
        exp.Next()
    return out


def sew_at(faces: list, tol: float) -> SewResult:
    """Sew a list of faces at a single tolerance and measure the result."""
    occ_utils.require_occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing

    sew = BRepBuilderAPI_Sewing(tol)
    sew.SetNonManifoldMode(False)
    sew.SetFloatingEdgesMode(False)
    for f in faces:
        sew.Add(f)
    sew.Perform()
    shape = sew.SewedShape()

    free, shared = occ_utils.free_and_shared_edges(shape)
    unsewn = occ_utils.coincident_free_edge_pairs(shape, tol=max(tol * 2, 1e-3))
    counts = occ_utils.count_subshapes(shape)
    return SewResult(
        shape=shape,
        tolerance=tol,
        n_faces=counts["faces"],
        n_shells=len(_iter_shells(shape)),
        n_free_edges=len(free),
        n_shared_edges=len(shared),
        n_unsewn_pairs=len(unsewn),
    )


def sew_progressive(faces: list, config: Config, name: str) -> SewResult:
    """Sew faces over the tolerance ladder, returning the best result.

    "Best" = fewest unsewn coincident seam pairs, tie-broken by fewer free edges.
    Stops early once zero unsewn pairs are achieved.

    Raises:
        ShellAssemblyError: If no faces are supplied.
    """
    if not faces:
        raise ShellAssemblyError(f"No faces to sew for {name}")

    best: SewResult | None = None
    for tol in config.sewing_tolerances:
        res = sew_at(faces, tol)
        logger.debug(
            "Sew %s @ tol=%.4g: faces=%d shells=%d free=%d shared=%d unsewn=%d",
            name,
            tol,
            res.n_faces,
            res.n_shells,
            res.n_free_edges,
            res.n_shared_edges,
            res.n_unsewn_pairs,
        )
        if best is None or (res.n_unsewn_pairs, res.n_free_edges) < (
            best.n_unsewn_pairs,
            best.n_free_edges,
        ):
            best = res
        if res.n_unsewn_pairs == 0:
            break

    assert best is not None
    logger.info(
        "Sewed %s: tol=%.4g faces=%d shells=%d free_edges=%d shared=%d unsewn_pairs=%d",
        name,
        best.tolerance,
        best.n_faces,
        best.n_shells,
        best.n_free_edges,
        best.n_shared_edges,
        best.n_unsewn_pairs,
    )
    return best


def heal_shell(shape):
    """Run ShapeFix_Shell on a sewn shape (no solid closure)."""
    occ_utils.require_occ()
    from OCC.Core.ShapeFix import ShapeFix_Shell
    from OCC.Core.TopAbs import TopAbs_SHELL

    shells = _iter_shells(shape)
    if len(shells) != 1:
        return shape
    fixer = ShapeFix_Shell(shells[0])
    fixer.SetFixFaceMode(True)
    fixer.Perform()
    healed = fixer.Shell()
    return healed if healed.ShapeType() == TopAbs_SHELL else shape
