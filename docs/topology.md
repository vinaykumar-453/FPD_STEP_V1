# Topology

## Engine body (the build set)

13 axisymmetric components, each stored as two circumferential FPD patches
(`inboard` 0°→180°, `outboard` 180°→360°) → 26 faces total.

| System | Components |
|--------|-----------|
| Intake | Spinner, Fan_face, Intake |
| Nacelle | Nacelle |
| Bypass | BP_inlet, BP_inner, BP_outer, BP_nozzle_Blunt_TE |
| Core | CR_inlet, CR_inner (centrebody), CR_outer, CR_TE, CR_nozzle_Blunt_TE |

Pylon (19 files) is excluded from geometry. CFD density zones (43 files) are
reconstructed into a separate compound node.

## Seams

- **Intra-component**: `inboard.B2 ↔ outboard.B3` and `inboard.B3 ↔ outboard.B2`
  (the two axial seams) per component.
- **Inter-component**: IS01–IS15 connect adjacent components (forward to aft).
  IS16 (pylon–nacelle) is excluded. See `topology/expected_topology.py`.

Seams are detected geometrically (`neighbour_detector`) by matching boundary
polylines with a symmetric KD-tree RMS/Hausdorff distance, then realised as
shared `TopoDS_Edge`s by sewing.

## Watertight (manifold) definition

The merged shell is **watertight** ⇔ **no two free edges are geometrically
coincident**. Interpretation:

- A free edge with a coincident partner = two faces meet but did not sew = an
  unsewn interface = **defect** (fails the gate).
- A free edge with no partner = a genuine open aerodynamic boundary (fan inlet,
  nozzle exits, nacelle aft, spinner/plug tips) = **allowed**.

This makes the gate independent of any hard-coded seam list while still
guaranteeing every internal interface is a single shared edge.

## Observed result (RB3135 dataset)

The 26 engine-body faces sew into **1 shell** with **52 shared edges** and **4
free edges** (the legitimate open boundaries), **0 unsewn coincident pairs** →
**watertight PASS**. The adjacency graph is a single connected component
covering all 13 components.
