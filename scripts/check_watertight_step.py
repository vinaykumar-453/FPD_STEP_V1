#!/usr/bin/env python
"""Re-load a written STEP file from disk and re-run the project's watertight gate.

This is a *round-trip* check: it does not trust the build-time report, it reads
the actual .step file back through OpenCASCADE and re-applies the project policy:

    watertight == no two free edges are geometrically coincident
    (free edges with no coincident partner are legitimate open aero boundaries)

It also reports the *strict* solid verdict (BRepCheck_Analyzer + free-edge
analysis): a fully sealed, valid solid with zero free edges. This is stricter
than the project policy and will FAIL whenever legitimate open aero boundaries
remain -- that is expected for this engine model.

Usage:
    conda run -n rb3135 python scripts/check_watertight_step.py output/RB3135.step
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from OCC.Core.BRepCheck import BRepCheck_Analyzer  # type: ignore
from OCC.Core.IFSelect import IFSelect_RetDone  # type: ignore
from OCC.Core.STEPControl import STEPControl_Reader  # type: ignore
from OCC.Core.TopAbs import TopAbs_SHELL, TopAbs_SOLID  # type: ignore
from OCC.Core.TopExp import TopExp_Explorer  # type: ignore

from engine_reconstruction.geometry import occ_utils

TOL = 1e-2  # config.free_edge_open_boundary_tol


def _count_type(shape, typ: int) -> int:
    exp = TopExp_Explorer(shape, typ)
    n = 0
    while exp.More():
        n += 1
        exp.Next()
    return n


def strict_solid_verdict(shape, n_free_edges: int) -> bool:
    """Strict closed-solid verdict (independent of the project policy).

    A shape passes only if it is BRepCheck-valid, contains at least one solid,
    and has zero free (single-face) edges -- i.e. a fully sealed manifold solid.
    ``n_free_edges`` is the authoritative incidence-based free-edge count from
    the policy check above (a sealed solid has none).
    """
    n_solids = _count_type(shape, TopAbs_SOLID)
    n_shells = _count_type(shape, TopAbs_SHELL)
    is_valid = BRepCheck_Analyzer(shape, True).IsValid()

    print("\n--- strict closed-solid verdict (BRepCheck_Analyzer) ---")
    print(f"solids              : {n_solids}")
    print(f"shells              : {n_shells}")
    print(f"BRepCheck IsValid   : {is_valid}")
    print(f"free (single-face) edges: {n_free_edges}  (must be 0 for a sealed solid)")

    passed = bool(is_valid and n_solids >= 1 and n_free_edges == 0)
    print(f"STRICT SOLID: {'PASS' if passed else 'FAIL'}")
    return passed


def read_step(path: str):
    reader = STEPControl_Reader()
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise SystemExit(f"Failed to read STEP: {path}")
    reader.TransferRoots()
    return reader.OneShape()


def main(path: str) -> int:
    occ_utils.require_occ()
    shape = read_step(path)

    counts = occ_utils.count_subshapes(shape)
    free, shared = occ_utils.free_and_shared_edges(shape)
    pairs = occ_utils.coincident_free_edge_pairs(shape, tol=TOL)

    print(f"file                : {path}")
    print(f"faces               : {counts['faces']}")
    print(f"edges               : {counts['edges']}")
    print(f"vertices            : {counts['vertices']}")
    print(f"shared edges        : {len(shared)}")
    print(f"free edges          : {len(free)}  (open aero boundaries if unpaired)")
    print(f"coincident free pairs: {len(pairs)}  (must be 0 for watertight)")

    if pairs:
        print("\nUNSEWN INTERFACES (defects):")
        for i, j, d in pairs:
            mid = occ_utils.edge_sample_points(free[i], 2).mean(axis=0)
            print(f"  edges {i}<->{j}  dist={d:.6g}  near={[round(float(v),4) for v in mid]}")

    policy_pass = len(pairs) == 0
    print(f"\nWATERTIGHT (project policy): {'PASS' if policy_pass else 'FAIL'}")

    strict_solid_verdict(shape, len(free))

    # Exit code reflects the project policy (the gate the pipeline enforces);
    # the strict solid verdict is informational.
    return 0 if policy_pass else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "output/RB3135.step"))
