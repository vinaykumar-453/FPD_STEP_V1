# Architecture

The framework is a layered reconstruction engine. Each module has one
responsibility, typed inputs/outputs, logging, and unit tests. Dependencies flow
strictly downward; OpenCASCADE is confined to the lower-right layers.

```
                     pipeline/engine_pipeline  (orchestrator)
                                  │
   ┌───────────┬──────────┬──────┴──────┬─────────────┬───────────┐
   │           │          │             │             │           │
  io/        grid/     topology/     geometry/    validation/   export/
discovery  validate   orientation    bspline      geometry      step
parser     statistics neighbour      face/heal    topology      (AP214)
metadata   downsample analyser       shell/solid  watertight
cache                 graph          shared_edge
                                     occ_utils
                                  │
                       infrastructure/ (config, logging, exceptions,
                       settings, provenance, data_types)
```

## Layer responsibilities

| Layer | Depends on | OCC? | Responsibility |
|-------|-----------|------|----------------|
| infrastructure | numpy | no | config, logging, exceptions, shared dataclasses, provenance |
| io | infrastructure | no | discover + classify files; parse FPD (ICEM/Tecplot/PLOT3D); cache; metadata |
| grid | io, infra | no | validate grids; statistics; optional downsampling |
| topology | grid, io, infra | no | orientation recovery; classification; adjacency graph; seam matching |
| geometry | topology, infra | **yes** | B-spline surfaces, faces, healing, sewing, compounds |
| validation | geometry, topology | **yes** | geometry/topology validity; **watertight hard gate** |
| export | geometry | **yes** | STEP AP214 writing |
| pipeline | all | yes (lazy) | stage orchestration, timing, provenance, reporting |

The io/grid/topology layers import only numpy/scipy, so they unit-test without
pythonocc-core. The pipeline imports OCC lazily inside `run()` so the module is
importable anywhere.

## Failure policy

The merged-shell **watertight gate** is the single hard requirement. Under
`strict_watertight` (default), a failure raises `WatertightnessError`; the
pipeline writes diagnostics and exits with code `2`, producing **no** STEP file.
Other reconstruction errors exit `1`. Success exits `0`.

## Export backend note

`STEPControl_Writer` is the default export backend (robust across OCC builds).
The XCAF backend (`use_xcaf=True`) embeds product *names* but the XCAF document
driver segfaults in some conda-forge OCC 7.9 builds, so it is opt-in. With the
default backend the three product nodes are conveyed by the nested-compound
hierarchy of `RB3135.step`.
