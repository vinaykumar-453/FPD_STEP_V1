# I/O Contracts

The typed dataclasses in `infrastructure/data_types.py` are the contracts passed
between stages.

## FPD file format (input)

ICEM native (the RB3135 dataset):

```
<ni> <nj>
x0 y0 z0
x1 y1 z1
...            # exactly ni*nj rows, points in file order (i-fastest)
```

Also accepted: Tecplot POINT (`ZONE I= J= F=POINT`), Tecplot BLOCK
(`F=BLOCK`), and single-grid ASCII PLOT3D. Detection is by content
(`io/fpd_parser.detect_format`). Units are metres.

## Stage contracts

| Stage | Input | Output |
|-------|-------|--------|
| discovery | `Config` | `list[FpdFile]` |
| parse | `Path` | `ParsedFpd` (coords in file order + ni, nj) |
| orientation | `ParsedFpd` | `StructuredGrid` `(nu, nv, 3)` |
| grid validation | `StructuredGrid`, `Config` | `GridValidationReport` |
| topology | `list[FpdFile]`, `{stem: StructuredGrid}` | `TopologyResult` |
| boundary | `StructuredGrid` | `list[BoundaryCurve]` |
| seam match | grids | `list[SeamMatch]` |
| fit | `StructuredGrid` | `SurfaceFitResult` (Geom_BSplineSurface) |
| face | `SurfaceFitResult` | `FaceRecord` (TopoDS_Face) |
| sew | `list[face]` | `SewResult` (shape + edge stats) |
| watertight | shell | `WatertightReport` (raises on hard fail) |
| export | shapes | `ExportResult` (RB3135.step) |

## Grid boundary convention

For a grid `G` of shape `(nu, nv, 3)`:

- `B0 = G[0, :]`   forward / inner-radial station
- `B1 = G[-1, :]`  aft / outer-radial station
- `B2 = G[:, 0]`   circumferential seam at v=0
- `B3 = G[:, -1]`  circumferential seam at v=N-1

## Environment overrides

`RB3135_FPD_DIR`, `RB3135_OUTPUT_DIR`, `RB3135_TOPOLOGY_CSV` (`none` disables),
`RB3135_DOWNSAMPLE`, `RB3135_NO_DENSITY`. CLI flags: `--fpd-dir`,
`--output-dir`, `--no-density`, `--no-pylon`, `--no-pylon-aux`,
`--with-components`, `--downsample`, `--strict`.
