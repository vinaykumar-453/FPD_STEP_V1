"""Reference topology of the RB3135 engine body (re-expressed, not copied).

Encodes the 13 axisymmetric engine-body components (S01-S13), their systems,
their intra-component seam convention, and the inter-component seam register
(IS01-IS15, pylon-excluded). These constants are used for *reporting* and to
cross-check the auto-derived / CSV-overridden topology. The hard watertight
gate itself is geometric (coincident-free-edge detection), so it does not
depend on the exact label pairings below.
"""

from __future__ import annotations

from dataclasses import dataclass

# Canonical component keys (file stem with _inboard/_outboard and the
# _free-flying suffix removed). Order = forward-to-aft assembly order.
ENGINE_BODY_COMPONENTS: tuple[str, ...] = (
    "Spinner",
    "Fan_face",
    "Intake",
    "Nacelle",
    "BP_inlet",
    "BP_inner",
    "BP_outer",
    "BP_nozzle_Blunt_TE",
    "CR_inlet",
    "CR_inner",
    "CR_outer",
    "CR_TE",
    "CR_nozzle_Blunt_TE",
)

SYSTEM_OF_COMPONENT: dict[str, str] = {
    "Spinner": "Intake",
    "Fan_face": "Intake",
    "Intake": "Intake",
    "Nacelle": "Nacelle",
    "BP_inlet": "Bypass",
    "BP_inner": "Bypass",
    "BP_outer": "Bypass",
    "BP_nozzle_Blunt_TE": "Bypass",
    "CR_inlet": "Core",
    "CR_inner": "Core",
    "CR_outer": "Core",
    "CR_TE": "Core",
    "CR_nozzle_Blunt_TE": "Core",
}


@dataclass(frozen=True)
class InterSeam:
    """A named inter-component interface (Surface A boundary ~ Surface B boundary)."""

    seam_id: str
    component_a: str
    component_b: str
    description: str


# Inter-component seams from the topology map (IS01-IS15; IS16 is pylon -> excluded).
INTER_COMPONENT_SEAMS: tuple[InterSeam, ...] = (
    InterSeam("IS01", "Spinner", "Fan_face", "Spinner aft / fan hub"),
    InterSeam("IS02", "Fan_face", "Intake", "Fan tip / intake inner aft"),
    InterSeam("IS03", "Intake", "Nacelle", "Highlight (intake lip / nacelle)"),
    InterSeam("IS04", "Nacelle", "BP_inlet", "Nacelle aft / BP inlet outer"),
    InterSeam("IS05", "BP_inlet", "Intake", "BP inlet inner / intake inner aft"),
    InterSeam("IS06", "BP_inlet", "BP_outer", "BP inlet outer / outer duct fwd"),
    InterSeam("IS07", "BP_inlet", "BP_inner", "BP inlet inner / inner duct fwd"),
    InterSeam("IS08", "BP_inner", "BP_nozzle_Blunt_TE", "Inner duct aft / nozzle TE inner"),
    InterSeam("IS09", "BP_outer", "BP_nozzle_Blunt_TE", "Outer duct aft / nozzle TE outer"),
    InterSeam("IS10", "CR_inlet", "CR_inner", "CR inlet inner / centrebody fwd"),
    InterSeam("IS11", "CR_inlet", "CR_outer", "CR inlet outer / core cowl fwd"),
    InterSeam("IS12", "CR_inner", "CR_TE", "Centrebody aft / core TE inner"),
    InterSeam("IS13", "CR_inner", "CR_nozzle_Blunt_TE", "Centrebody aft / nozzle TE inner"),
    InterSeam("IS14", "CR_outer", "CR_nozzle_Blunt_TE", "Core cowl aft / nozzle TE outer"),
    InterSeam("IS15", "CR_outer", "CR_TE", "Core cowl aft / core TE outer"),
)

# Pylon files split into two groups:
#   * FAIRING — the smooth pylon body that belongs to the engine assembly:
#     upper/lower aerofoil, top/bottom closing caps, and the heatshield.
#   * AUX — the 12 wing_cut / TE_cut construction/trim faces (large stray planes
#     used to trim the pylon to the wing); kept as a separate auxiliary node.
PYLON_AUX_MARKERS: tuple[str, ...] = ("wing_cut_off", "pylon_te_cut_")


def is_pylon_aux(stem: str) -> bool:
    """True for pylon construction/trim (cut) faces (the auxiliary node)."""
    lower = stem.lower()
    return any(m in lower for m in PYLON_AUX_MARKERS)


def is_pylon_fairing(stem: str) -> bool:
    """True for pylon fairing surfaces that join the engine assembly.

    Everything pylon that is *not* a cut/trim face: the upper/lower aerofoil,
    the top/bottom closing caps, and the heatshield.
    """
    return not is_pylon_aux(stem)


# Legitimate open aerodynamic boundaries (no caps; these MAY remain as free
# edges without coincident partners). Used only for reporting/explanation.
LEGITIMATE_OPEN_BOUNDARIES: tuple[str, ...] = (
    "Spinner nose tip (axis singularity)",
    "Fan Face inner annulus (fan inlet BC)",
    "Fan Face outer annulus (fan inlet BC)",
    "Nacelle aft trailing edge (farfield)",
    "BP Nozzle TE annular exit (nozzle outlet)",
    "CR TE plug tip",
    "CR Nozzle TE annular exit (nozzle outlet)",
)


def n_expected_intra_seams() -> int:
    """Two circumferential seams per 2-patch component."""
    return 2 * len(ENGINE_BODY_COMPONENTS)


def n_expected_inter_seams() -> int:
    return len(INTER_COMPONENT_SEAMS)
