"""Stage 9c — aggregate geometry validity checks over faces and shells.

Thin wrappers over ``BRepCheck_Analyzer`` plus surface-fit fidelity aggregation,
used by the pipeline to summarise per-surface geometry health.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..geometry import occ_utils
from ..infrastructure.data_types import FaceRecord, SurfaceFitResult
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GeometryValidationReport:
    """Aggregate geometry validity across all faces."""

    n_faces: int = 0
    n_valid_faces: int = 0
    n_fixed_faces: int = 0
    n_fit_warn: int = 0
    n_fit_fail: int = 0
    invalid_faces: list[str] = field(default_factory=list)
    max_area_deviation_pct: float = 0.0

    @property
    def passed(self) -> bool:
        return self.n_valid_faces == self.n_faces and self.n_fit_fail == 0


def is_valid(shape) -> bool:
    """Return ``BRepCheck_Analyzer`` validity for any shape."""
    occ_utils.require_occ()
    from OCC.Core.BRepCheck import BRepCheck_Analyzer

    return bool(BRepCheck_Analyzer(shape).IsValid())


def validate_geometry(
    faces: list[FaceRecord],
    fits: list[SurfaceFitResult],
    pass_pct: float,
) -> GeometryValidationReport:
    """Summarise face validity and fit fidelity."""
    rep = GeometryValidationReport(n_faces=len(faces))
    for fr in faces:
        if fr.valid:
            rep.n_valid_faces += 1
        else:
            rep.invalid_faces.append(fr.name)
        if fr.fixed:
            rep.n_fixed_faces += 1
    for fit in fits:
        rep.max_area_deviation_pct = max(rep.max_area_deviation_pct, fit.area_deviation_pct)
        if not fit.passed:
            rep.n_fit_fail += 1
        elif fit.area_deviation_pct > pass_pct:
            rep.n_fit_warn += 1
    logger.info(
        "Geometry validation: %d/%d faces valid, %d healed, fit warn=%d fail=%d, "
        "max area dev=%.3f%%",
        rep.n_valid_faces,
        rep.n_faces,
        rep.n_fixed_faces,
        rep.n_fit_warn,
        rep.n_fit_fail,
        rep.max_area_deviation_pct,
    )
    return rep
