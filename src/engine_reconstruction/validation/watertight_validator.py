"""Stage 11 — the hard watertight (manifold) gate on the merged engine shell.

Definition (per project policy): the merged shell is *watertight* when every
interface that should be shared **is** shared — equivalently, when **no two free
edges are geometrically coincident**. A free edge with no coincident partner is
a legitimate open aerodynamic boundary and is allowed; a coincident free-edge
pair means two faces meet there but failed to sew, which is a defect.

If ``config.strict_watertight`` is set, a failure raises
:class:`WatertightnessError` (the pipeline then hard-fails and writes no STEP).
"""

from __future__ import annotations

from ..geometry import occ_utils
from ..infrastructure.config import Config
from ..infrastructure.data_types import WatertightReport
from ..infrastructure.exceptions import WatertightnessError
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


def validate_watertight(
    shape,
    config: Config,
    expected_seams: int = 0,
) -> WatertightReport:
    """Validate the merged shell against the manifold/watertight criterion.

    Args:
        shape: The sewn merged shell (``TopoDS_Shell`` or compound).
        config: Run configuration (coincidence tolerance, strict flag).
        expected_seams: Number of interfaces expected to become shared edges
            (from geometric boundary matching); used for reporting.

    Returns:
        A :class:`WatertightReport`.

    Raises:
        WatertightnessError: If strict and the shell is not manifold.
    """
    occ_utils.require_occ()
    free, shared = occ_utils.free_and_shared_edges(shape)
    counts = occ_utils.count_subshapes(shape)
    tol = config.free_edge_open_boundary_tol
    pairs = occ_utils.coincident_free_edge_pairs(shape, tol=tol)

    unexpected: list[dict] = []
    for i, j, dist in pairs:
        pi = occ_utils.edge_sample_points(free[i], 2)
        mid = pi.mean(axis=0).tolist() if pi.size else [0.0, 0.0, 0.0]
        unexpected.append(
            {
                "edge_a": i,
                "edge_b": j,
                "distance": round(dist, 6),
                "near_xyz": [round(v, 4) for v in mid],
            }
        )

    passed = len(pairs) == 0
    report = WatertightReport(
        passed=passed,
        n_faces=counts["faces"],
        n_edges=counts["edges"],
        n_shared_edges=len(shared),
        n_free_edges=len(free),
        expected_seams_total=expected_seams,
        expected_seams_shared=len(shared),
        unexpected_free_edges=unexpected,
        notes=[
            "watertight == no coincident free-edge pairs (all interfaces shared)",
            (
                f"{len(free)} free edge(s) remain as legitimate open aero boundaries"
                if passed
                else f"{len(pairs)} coincident free-edge pair(s) indicate unsewn interfaces"
            ),
        ],
    )

    if passed:
        logger.info(
            "WATERTIGHT PASS: faces=%d edges=%d shared=%d free=%d (open boundaries)",
            report.n_faces,
            report.n_edges,
            report.n_shared_edges,
            report.n_free_edges,
        )
    else:
        logger.error(
            "WATERTIGHT FAIL: %d unsewn coincident free-edge pair(s); "
            "faces=%d free=%d shared=%d",
            len(pairs),
            report.n_faces,
            report.n_free_edges,
            report.n_shared_edges,
        )
        if config.strict_watertight:
            raise WatertightnessError(
                f"Merged engine shell is not manifold: {len(pairs)} unsewn "
                f"coincident free-edge pair(s). See diagnostic report."
            )
    return report
