# RB3135 Reconstruction — Build Notes & Reference

A self-contained record of how this framework was built, the decisions behind
it, the verified results, and the gotchas. Companion to `architecture.md`,
`io_contracts.md`, `topology.md`, and `assumptions.md`.

---

## 1. What this is

A clean-room Python framework that reconstructs a sewn, manifold B-Rep CAD model
of the RB3135 free-flying turbofan from GEMINI **FPD** surface point grids and
exports `output/RB3135.step` (AP214). One command:

```bash
conda run -n rb3135 python engine_pipeline.py
```

PURN 83, Cranfield (dissertation deliverable).

---

## 2. Input data (discovered, not assumed)

- **Location**: `/Users/vinaykumar/Downloads/ICEM_CAD_working_directory_spoof/FPD`
- **88 `.fpd` files** = **45 physical** (26 engine body + 19 pylon) + **43 CFD density zones**.
- **Real format is custom ICEM**, NOT Tecplot/PLOT3D:
  - line 1 = `ni nj`; then `ni*nj` lines of `X Y Z` (ASCII, metres, double precision).
  - Point order is **i-fastest** (column-major). Wrong reshape → twisted surfaces.
- Reference artifacts (read-only, used as optional override / ground-truth):
  - `…/PY/rb3135_topology.csv` — physical/CFD classification + adjacency.
  - `/Users/vinaykumar/Downloads/RB3135_FreeFlying_Engine_Topology_Map.md` — seam map IS01–IS16, open-boundary register.

---

## 3. Locked decisions (from the user, via clarification)

| # | Decision |
|---|----------|
| 1 | **Clean-room rebuild** in `/Users/vinaykumar/Downloads/2.0`; do not copy prior code. |
| 2 | Parser supports **ICEM + Tecplot POINT/BLOCK + PLOT3D** (one extensible interface). |
| 3 | Topology **hybrid**: auto-derive from geometry, optional CSV override/validate. |
| 4 | **Build set = 26 engine-body surfaces (S01–S13)**; parse+validate all 88; pylon excluded. |
| 5 | **"Watertight" = sewn manifold shell, no caps**; hard gate = no coincident free-edge pairs. Hard-fail (exit 2, no STEP) if unmet. |
| 6 | Output = one `RB3135.step` (AP214) with merged shell + 13-component compound + CFD-density compound. |
| 7 | **Full-resolution** B-spline fitting (downsampling off by default). |
| 8 | **Fresh conda env** `rb3135`, pythonocc-core (conda-forge), Python 3.12. |
| 9 | **Build and run end-to-end now** against the real 88 files. |

> The original "88 → fall back to 42" escalation was superseded by the more
> specific later choices (exclude pylon, manifold-shell, build-from-26).

---

## 4. Verified results

```
Discovered FPD files: 88  (engine_body=26, pylon=19, cfd_density=43)
Grids valid: 62  (26 rejected = CFD density polar base-caps; engine body 26/26 OK)
Topology: components=13/13, seam_matches=64, graph_connected=True (1 component)
Engine-body faces: 26/26 valid, max area deviation 0.010%
Merged shell: faces=26 shells=1 shared=52 free=4 unsewn_pairs=0 (sew tol=0.001)
WATERTIGHT PASS
STEP written: output/RB3135.step (AP214IS, 1.77 MB)  ->  exit 0
Readback: 69 faces, BRep valid = True
```

Quality gates: **pytest** 31 pass / 1 skip · **mypy** clean · **ruff** clean · **black** clean.

---

## 5. Key algorithms

- **Orientation recovery** (`topology/orientation_detector.py`): build both
  i-fastest and j-fastest reshapes, pick the one with smaller total polyline
  length (minimises ring scatter). Real-data roughness ratios 4–54× → unambiguous.
- **Seam detection** (`topology/neighbour_detector.py`): KD-tree symmetric RMS +
  Hausdorff between the four boundary polylines (B0–B3) of every surface pair.
- **B-spline fit** (`geometry/bspline_builder.py`): `GeomAPI_PointsToBSplineSurface`,
  continuity C2→C1→C0 fallback, degree 3–8, tol 1e-4, area-deviation gate.
- **Sewing** (`geometry/shell_builder.py`): `BRepBuilderAPI_Sewing` over a
  tolerance ladder `[1e-3 … 1.0] m`, picking the tol with fewest unsewn coincident
  pairs; non-manifold off, solid-mode off (no forced caps).
- **Watertight gate** (`validation/watertight_validator.py`): pass ⇔ **no two free
  edges are geometrically coincident** (every interface became a shared edge;
  genuine open boundaries have no partner). Raises `WatertightnessError` if strict.

---

## 6. Gotchas / lessons (important for future work)

1. **XCAF segfaults** in this conda-forge **OCC 7.9** build: constructing
   `TDocStd_Document` crashes the process (uncatchable C++ fault), even after
   `binxcafdrivers.DefineFormat`. → Default export uses `STEPControl_Writer`
   (robust); XCAF is opt-in (`use_xcaf=True`). Product nodes conveyed via nested
   compounds.
2. **`TopTools_IndexedDataMapOfShapeListOfShape`** uses `.Size()`, **not**
   `.Extent()`, in pythonocc 7.9.
3. **pythonocc stubs are imperfect** (indexed-map ctors, `TColgp_Array2OfPnt`
   4-arg ctor, XCAF `Set`/`AddShape`): handled with localized
   `# mypy: disable-error-code=...` headers, not project-wide loosening.
4. **CFD density polar base-caps** (central-collapse discs) are flagged degenerate
   by the grid validator and rejected → some density zones reconstruct without
   caps. Acceptable: density is auxiliary, engine body unaffected.
5. **Env**: `base` conda env lacks OCC. Always run in `rb3135`
   (`conda run -n rb3135 …`). Dev tools (pytest/mypy/ruff/black) were
   `pip install`-ed into `rb3135` on top of the conda env.

---

## 7. Reproduce / verify

```bash
conda env create -f environment.yml                 # creates rb3135
conda run -n rb3135 pip install pytest mypy ruff black
conda run -n rb3135 python engine_pipeline.py        # -> output/RB3135.step
conda run -n rb3135 python -m pytest -q
conda run -n rb3135 ruff check src tests
conda run -n rb3135 black --check src tests
conda run -n rb3135 mypy src
```

Useful flags: `--no-density`, `--no-pylon`, `--no-pylon-aux`, `--with-components`,
`--downsample`, `--strict`, `--fpd-dir`, `--output-dir`.

## 9. Watertight-assembled, config-driven revision

Final target: a generic, config-driven framework producing ONE STEP with a
**watertight assembled engine** plus everything else as separate nodes.

- **Output nodes**: `RB3135_Engine_Assembly` (26 engine-body + 7 pylon fairing
  faces incl. heatshield, sewn), `RB3135_Pylon_Aux` (12 cut/trim faces),
  `RB3135_CFD_Density_Zones` (43 density shells). `step_exporter.export_step` now
  takes an ordered `(name, shape)` node list.
- **Watertight** = one connected sewn shell, open inlets/outlets allowed,
  best-effort (always writes; `--strict` to hard-fail). The engine **body** sews
  to a single watertight shell (52 shared edges, 4 open boundaries, 0 gaps);
  adding the pylon yields a few extra shells because the pylon meets the nacelle
  by surface contact, not edge coincidence (a true single fused shell would need
  boolean imprinting — out of scope). Reported, not hidden.
- **Pylon split**: `expected_topology.is_pylon_fairing` (assembly) vs
  `is_pylon_aux` (cut/trim).
- **Config-driven**: input is `Config.fpd_dir` (env/CLI overridable); the
  name-spec turbofan skeleton maps any conformantly-named FPD set onto the engine.
- Guard fix: `occ_utils.coincident_free_edge_pairs` returns early when a sewn
  shape has <2 free edges (was crashing on the pylon-aux node).

## 8. Visual-fidelity revision (after first delivery)

The first STEP was technically correct but visually unusable: it overlaid the
huge CFD density cylinders + duplicate component geometry and omitted the pylon.
Revised so the default output is a clean, recognizable engine:

- **Default = engine body (26) + visible pylon (4) only**; density and component
  compounds are opt-in (`--with-density`, `--with-components`).
- **Pylon**: aerofoil fairing only (upper/lower aerofoil + top/bottom closing,
  4 faces). Excluded: the 12 `wing_cut`/`TE_cut` construction faces AND the 3
  heatshield faces (they sew into a small detached tubular shell that reads as a
  stray "barrel" near the nozzle — user-flagged for removal).
- **Pylon heatshield has 2.78M points** → capped (`pylon_fit_cap`) before fitting,
  else `GeomAPI_PointsToBSplineSurface` hangs.
- **B-spline overshoot guard**: high-degree approximation ballooned pylon panels
  to ~11 km. The fitter now checks control-pole extent vs the grid bbox and falls
  back C2→C1→C0→bilinear (or rejects). Detect overshoot via **poles** (convex-hull
  property), not point sampling — sampling misses sharp inter-sample spikes.
- **Watertight** is now best-effort by default (engine body reported every run);
  `--strict` restores the hard gate.
- Headless render: `engine_reconstruction.visualization.render.render_step`
  (tessellate + matplotlib; OCC offscreen needs a Cocoa/GUI context).

Reports land in `output/reports/` (`pipeline_summary.txt`, `provenance.json`,
`watertight_report.json`, `topology_*.json`, `geometry_validation.json`,
`surface_metadata.csv`).
