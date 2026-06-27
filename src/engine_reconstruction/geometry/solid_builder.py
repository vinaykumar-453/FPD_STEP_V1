"""Stage 12 — solid / compound construction.

Per project policy the RB3135 free-flying engine is reconstructed as a sewn
*manifold shell*, not a closed ``TopoDS_Solid``: its aerodynamic surfaces are
intentionally open (fan inlet, nozzle exits, nacelle aft, spinner/plug tips) and
must remain wall/BC faces for CFD. Forcing closure would inject non-physical cap
faces, so we do not.

This module therefore provides compound assembly helpers and an *opportunistic*
``make_solid_if_closed`` that only yields a solid when a shell is genuinely
closed (e.g. the CFD density cylinders), never by adding caps.
"""

from __future__ import annotations

from typing import Any

from ..infrastructure.logging import get_logger
from . import occ_utils

logger = get_logger(__name__)


def make_compound(shapes: list) -> Any:
    """Combine shapes into a single ``TopoDS_Compound``."""
    occ_utils.require_occ()
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound

    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for s in shapes:
        if s is not None:
            builder.Add(compound, s)
    return compound


def is_closed_shell(shell) -> bool:
    """Return True if a shell has no free edges (topologically closed)."""
    occ_utils.require_occ()
    free, _ = occ_utils.free_and_shared_edges(shell)
    return len(free) == 0


def make_solid_if_closed(shell) -> Any | None:
    """Return a ``TopoDS_Solid`` if the shell is closed, else ``None``.

    Never adds caps; closure must already exist in the geometry.
    """
    occ_utils.require_occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeSolid

    if not is_closed_shell(shell):
        return None
    mk = BRepBuilderAPI_MakeSolid(shell)
    if not mk.IsDone():
        return None
    return mk.Solid()
