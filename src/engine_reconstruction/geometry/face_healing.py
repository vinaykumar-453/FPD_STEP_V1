"""Stage 9b — heal and validate a face.

Runs ``ShapeFix_Face`` to repair wires/orientation and reports BRep validity via
``BRepCheck_Analyzer``. Solid-mode fixing is intentionally *not* applied: the
engine surfaces are open aerodynamic shells and must not be force-closed.
"""

from __future__ import annotations

from ..infrastructure.logging import get_logger
from . import occ_utils

logger = get_logger(__name__)


def is_valid(shape) -> bool:
    """Return True if ``BRepCheck_Analyzer`` reports the shape as valid."""
    occ_utils.require_occ()
    from OCC.Core.BRepCheck import BRepCheck_Analyzer

    return bool(BRepCheck_Analyzer(shape).IsValid())


def heal_face(face, name: str) -> tuple[object, bool, bool]:
    """Heal a face with ShapeFix_Face.

    Args:
        face: Input ``TopoDS_Face``.
        name: Surface name (for logging).

    Returns:
        Tuple ``(healed_face, was_fixed, is_valid)``.
    """
    occ_utils.require_occ()
    from OCC.Core.ShapeFix import ShapeFix_Face

    before_valid = is_valid(face)
    fixer = ShapeFix_Face(face)
    fixer.SetPrecision(1e-6)
    changed = bool(fixer.Perform())
    fixer.FixOrientation()
    healed = fixer.Face()
    after_valid = is_valid(healed)
    if changed and not before_valid:
        logger.debug("Healed face %s (valid %s -> %s)", name, before_valid, after_valid)
    return healed, changed, after_valid
