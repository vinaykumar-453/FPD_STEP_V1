"""Stage 7 — shared edge reconstruction (topology bookkeeping).

In an OpenCASCADE B-Rep, a shared edge is created when ``BRepBuilderAPI_Sewing``
merges two coincident face boundaries. There must be exactly **one**
``TopoDS_Edge`` per interface, referenced by both adjacent faces — never a
duplicate.

This module derives, from the geometrically-detected boundary matches, the set
of interfaces that *should* become shared edges after sewing. The watertight
validator then checks that they did.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..infrastructure.data_types import SeamMatch
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExpectedSeam:
    """A canonical, direction-independent interface between two boundaries."""

    surface_a: str
    boundary_a: str
    surface_b: str
    boundary_b: str
    rms: float

    @property
    def key(self) -> tuple[str, str, str, str]:
        a = (self.surface_a, self.boundary_a)
        b = (self.surface_b, self.boundary_b)
        lo, hi = sorted((a, b))
        return (*lo, *hi)


def expected_shared_seams(matches: list[SeamMatch]) -> list[ExpectedSeam]:
    """Collapse boundary matches into the unique interfaces to be shared.

    Each unordered ``(surface, boundary)`` pair is reported once, keeping the
    smallest observed RMS.
    """
    best: dict[tuple[str, str, str, str], ExpectedSeam] = {}
    for m in matches:
        seam = ExpectedSeam(
            surface_a=m.surface_a,
            boundary_a=m.boundary_a.value,
            surface_b=m.surface_b,
            boundary_b=m.boundary_b.value,
            rms=m.rms,
        )
        existing = best.get(seam.key)
        if existing is None or seam.rms < existing.rms:
            best[seam.key] = seam
    seams = sorted(best.values(), key=lambda s: s.key)
    logger.info(
        "Expected %d unique shared interface(s) from %d boundary matches", len(seams), len(matches)
    )
    return seams
