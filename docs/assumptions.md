# Assumptions & Limitations

## Core assumption

A watertight result is only achievable if the FPD dataset collectively defines
every external surface and their interfaces. The framework reconstructs
geometry, topology, and B-Rep entities from the sampled grids; **it cannot invent
missing surfaces**. When interfaces are not coincident in the data, the hard gate
reports exactly which ones failed rather than fabricating geometry.

## "Watertight" means a sewn manifold shell, not a closed solid

The RB3135 free-flying engine surfaces are intentionally **open** aerodynamic
walls (CFD boundary conditions). They do not bound a volume. We therefore deliver
a sewn **manifold shell** (`TopoDS_Shell`) in which every interface is a shared
edge and only legitimate aerodynamic openings remain free. No caps are added;
`make_solid_if_closed` only produces a solid for genuinely closed shells (it does
not apply to the open engine body).

## Scope decisions

- **Pylon excluded** from the geometry (its 19 cut/compound patches are out of
  scope for the axisymmetric watertight body).
- **CFD density zones** are reconstructed best-effort into a separate compound
  node and never affect the engine watertight gate.

## Known limitations

- **Density polar base-caps**: several density cylinder end-caps are polar discs
  whose grids collapse many points at the centre. The grid validator flags these
  as degenerate (excessive duplicate adjacent points) and rejects them, so some
  density zones reconstruct without caps. This is acceptable because density
  zones are auxiliary; the engine-body grids are unaffected.
- **XCAF naming**: embedding product *names* via `STEPCAFControl_Writer` requires
  the XCAF document driver, which segfaults in some conda-forge OCC 7.9 builds.
  The default export uses `STEPControl_Writer` and conveys the three product
  nodes via the nested-compound hierarchy. Pass `use_xcaf=True` where the driver
  works to embed names.
- **Full-resolution fitting** can be slow on the largest grids (~1090×200);
  enable `--downsample` for faster iteration at some fidelity cost.
