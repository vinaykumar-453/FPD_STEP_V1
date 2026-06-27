# RB3135 FPD → Watertight STEP Reconstruction Framework

Automatically reconstructs a sewn, manifold B-Rep CAD model of the **RB3135
free-flying turbofan** from GEMINI **FPD** surface point-grid files and exports
it as a **STEP AP214** file — suitable for CFD meshing and CAD interoperability.

> PURN 83 — *Application of Advanced CAD Modelling for Civil Aero Engine Exhaust
> System and Pylon Design* (Cranfield University).

```bash
conda env create -f environment.yml      # creates the 'rb3135' env (pythonocc-core)
conda run -n rb3135 python engine_pipeline.py
```

The single command discovers the FPD files, parses + validates every grid,
recovers topology, fits B-spline surfaces, builds & heals faces, sews them into
shells, enforces the watertight (manifold) gate, reconstructs the CFD density
zones, and writes `output/RB3135.step`.

## What the FPD files are

Each `.fpd` is **not CAD** — it is a structured point grid: line 1 is `ni nj`,
followed by `ni × nj` lines of `X Y Z` (metres). The framework *reconstructs*
CAD geometry and topology from these samples.

## Reconstruction pipeline

```
FPD files → discovery → parse → orientation recovery → grid validation
          → topology recovery → boundary extraction → seam matching
          → B-spline fit → faces (+heal) → shells (sew) → watertight gate
          → CFD density compound → STEP AP214 export
```

## Key design decisions

The default output is **one `RB3135.step` (AP214)** containing a single node —
the clean **watertight engine** — so a CAD viewer shows the engine, not the CFD
domain:

| STEP node | When | Contents |
|-----------|------|----------|
| `RB3135_Engine_Assembly` | always | **Watertight assembled engine** — 26 engine-body surfaces + the 7 pylon fairing surfaces (upper/lower aerofoil, top/bottom closing caps, heatshield) sewn together. |
| `RB3135_Pylon_Aux` | `--with-pylon-aux` | The 12 pylon `wing_cut`/`TE_cut` construction/trim faces (large stray planes ~43 m). |
| `RB3135_CFD_Density_Zones` | `--with-density` | The 43 CFD density zones (large CFD-domain cylinders). |

> The pylon trim planes and density cylinders are huge auxiliary surfaces that
> visually bury the engine, so they are **off by default** and added only on
> request.

| Decision | Rationale |
|----------|-----------|
| **Generic + config-driven** | FPD files are read from `Config.fpd_dir` (overridable via `RB3135_FPD_DIR` / `--fpd-dir`). Point it at any turbofan FPD folder that follows the RB3135 naming convention and it reconstructs that engine — the file *count* doesn't matter. |
| **Name-spec turbofan skeleton (prefix match)** | The 13-component skeleton (`ENGINE_BODY_COMPONENTS`) drives the engine. Each surface is assigned to a component by **prefix match** (e.g. `BP_inner_inboard_installed` → `BP_inner`), so role and configuration suffixes are tolerated automatically. |
| **Multiple configurations** | When a dataset ships `_installed` / `_uninstalled` variants of every surface, select one with `--configuration installed` (default) or `--configuration uninstalled` / `RB3135_CONFIGURATION`. Untagged files (e.g. `_free-flying`) are always included. Suffixes `_free-flying` / `_installed` / `_uninstalled` are stripped before classification. |
| **"Watertight" = one connected sewn shell, no caps** | All engine-assembly faces are sewn so every internal interface is a shared edge; the real intake/fan-face/nozzle openings stay open. Watertight ⇔ no two free edges are coincident — **reported** every run. Best-effort by default; `--strict` hard-fails if not manifold. The engine *body* sews to a single watertight shell; the pylon attaches by surface contact, so it adds shells within the assembly (boolean imprinting would be needed to fuse them — out of scope). |
| **Engine-only by default; extras opt-in** | Default = the watertight engine assembly only. Add the CFD density zones with `--with-density` and the pylon trim planes with `--with-pylon-aux` (each as its own node); `--no-pylon` drops the pylon. |
| **Full-resolution engine fitting + overshoot guard** | Engine surfaces fit at full resolution (C2, deg 3–8); a pole-based overshoot guard refits/rejects any surface that balloons outside its point cloud (pylon panels). Oversized pylon grids are capped for tractable fitting. |

### Visual check

Render just the watertight engine-assembly node (the full file also contains the
large trim/density nodes):

```bash
conda run -n rb3135 python -c "import sys; sys.path.insert(0,'src'); \
from pathlib import Path; from OCC.Core.STEPControl import STEPControl_Reader; \
from OCC.Core.TopoDS import TopoDS_Iterator; \
from engine_reconstruction.visualization.render import render_shape; \
r=STEPControl_Reader(); r.ReadFile('output/RB3135.step'); r.TransferRoots(); \
render_shape(TopoDS_Iterator(r.OneShape()).Value(), Path('output/renders/asm'))"
```

Writes `output/renders/asm_{iso,side,front}.png` (requires `matplotlib`).

## Architecture

```
src/engine_reconstruction/
  infrastructure/  config, logging, exceptions, settings, provenance, data_types
  io/              file_discovery, fpd_parser, metadata, cache
  grid/            grid_validator, grid_statistics, downsampling
  topology/        orientation_detector, neighbour_detector, topology_graph,
                   topology_analyser, expected_topology
  geometry/        bspline_builder, boundary_reconstruction, shared_edge_builder,
                   face_builder, face_healing, shell_builder, solid_builder, occ_utils
  validation/      geometry_validator, topology_validator, watertight_validator
  export/          step_exporter
  visualization/   diagnostics, viewer
  pipeline/        engine_pipeline
```

The io / grid / topology / infrastructure layers depend only on NumPy/SciPy and
are unit-testable without OpenCASCADE; OCC is isolated to geometry / validation /
export.

## Outputs

Everything lands under `output/`:

- `RB3135.step` — the reconstructed model (on success).
- `reports/` — `pipeline_summary.txt`, `provenance.json`, `watertight_report.json`,
  `topology_*.json`, `geometry_validation.json`, `surface_metadata.csv`, …
- `reconstruction.log` — full run log.

## Development

```bash
conda run -n rb3135 python -m pytest         # unit + integration tests
conda run -n rb3135 ruff check src tests
conda run -n rb3135 black --check src tests
conda run -n rb3135 mypy src
```

## Important assumption

A watertight result is only achievable if the FPD dataset collectively defines
every external surface and interface. The framework reconstructs geometry and
topology from the samples; it cannot invent missing surfaces. When interfaces
are not coincident in the data, the hard gate reports exactly which ones failed.
