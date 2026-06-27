"""Stage 9a — build a TopoDS_Face from a fitted B-spline surface."""

from __future__ import annotations

from ..infrastructure.config import Config
from ..infrastructure.data_types import FaceRecord, SurfaceFitResult
from ..infrastructure.exceptions import FaceConstructionError
from ..infrastructure.logging import get_logger
from . import face_healing, occ_utils

logger = get_logger(__name__)


def build_face(fit: SurfaceFitResult, config: Config) -> FaceRecord:
    """Construct, heal, and validate a face for a fitted surface.

    Args:
        fit: The B-spline surface fit result.
        config: Run configuration (face tolerance).

    Returns:
        A :class:`FaceRecord` with the healed face and validity flag.

    Raises:
        FaceConstructionError: If the face cannot be built at all.
    """
    occ_utils.require_occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    mk = BRepBuilderAPI_MakeFace(fit.surface, config.face_tol)
    if not mk.IsDone():
        raise FaceConstructionError(f"MakeFace failed for {fit.name}")
    face = mk.Face()

    healed, fixed, valid = face_healing.heal_face(face, fit.name)
    if not valid:
        logger.warning("Face %s is not BRep-valid after healing", fit.name)
    return FaceRecord(
        name=fit.name,
        face=healed,
        valid=valid,
        fixed=fixed,
        grid_name=fit.name,
    )
