"""The automated RB3135 reconstruction pipeline.

Orchestrates all 13 stages from FPD discovery to STEP export. Running

    python engine_pipeline.py

(via the repo-root wrapper) executes :func:`main`, which builds a
:class:`Config`, runs :func:`run`, and returns a process exit code.

Policy:
  * The watertight (manifold) check on the merged engine shell is a **hard
    gate**: if it fails under ``strict_watertight`` the pipeline writes a
    diagnostic report and exits non-zero **without** producing a STEP file.
  * CFD density zones are reconstructed as a separate compound node and never
    affect the engine-shell gate.
"""

from __future__ import annotations

import argparse
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..grid import downsampling, grid_validator
from ..infrastructure import logging as log_setup
from ..infrastructure.config import Config
from ..infrastructure.data_types import StructuredGrid, SurfaceClass
from ..infrastructure.exceptions import ReconstructionError, WatertightnessError
from ..infrastructure.logging import get_logger
from ..infrastructure.provenance import Provenance, detect_occ
from ..infrastructure.settings import load_config
from ..io import file_discovery, fpd_parser
from ..io.cache import GridCache
from ..io.metadata import MetadataRegistry
from ..topology import expected_topology, orientation_detector, topology_analyser
from ..visualization import diagnostics

logger = get_logger(__name__)

_FREE_FLYING = re.compile(r"[_-]free[_-]flying$", re.IGNORECASE)


def _density_zone_key(stem: str) -> str:
    """Group a density file into its zone (e.g. ``Jet_density_1``)."""
    base = _FREE_FLYING.sub("", stem)
    key = re.split(r"_cylindrical", base, flags=re.IGNORECASE)[0]
    return re.sub(r"_(outer|inner)$", "", key, flags=re.IGNORECASE)


@contextmanager
def _stage(prov: Provenance, name: str) -> Iterator[None]:
    """Time a stage and record its status in provenance."""
    logger.info("=== Stage: %s ===", name)
    t0 = time.perf_counter()
    try:
        yield
    except Exception as exc:
        prov.record_stage(name, "FAILED", time.perf_counter() - t0, error=str(exc))
        raise
    else:
        prov.record_stage(name, "OK", time.perf_counter() - t0)


def _load_grid(path: Path, name: str, cache: GridCache, config: Config) -> StructuredGrid:
    """Parse + orient (with cache) and optionally downsample a single FPD."""
    grid = cache.load(path, name)
    if grid is None:
        parsed = fpd_parser.parse_fpd(path)
        grid = orientation_detector.recover_orientation(parsed)
        cache.store(grid)
    return downsampling.downsample(grid, config)


def run(config: Config) -> int:
    """Execute the full pipeline.

    Args:
        config: Run configuration.

    Returns:
        Process exit code (0 success, non-zero failure).
    """
    # Lazy OCC imports keep the module importable without pythonocc-core.
    from ..export import step_exporter
    from ..geometry import (
        bspline_builder,
        face_builder,
        shared_edge_builder,
        shell_builder,
        solid_builder,
    )
    from ..validation import geometry_validator, topology_validator, watertight_validator

    out = config.resolved_output_dir()
    out.mkdir(parents=True, exist_ok=True)
    log_setup.configure_logging(log_file=out / "reconstruction.log")

    prov = Provenance(config={k: str(v) for k, v in vars(config).items()})
    prov.occ_available, prov.occ_version = detect_occ()
    cache = GridCache(out / "cache")
    registry = MetadataRegistry()
    summary: list[str] = ["RB3135 FPD -> STEP reconstruction", "=" * 48]

    try:
        # --- Stage 1: discovery ---
        with _stage(prov, "discovery"):
            files = file_discovery.discover(config)
            files_by_stem = {f.stem: f for f in files}
            summary.append(f"Discovered FPD files: {len(files)}")

        # --- Stages 2-4: parse, orient, validate (all surfaces) ---
        grids: dict[str, StructuredGrid] = {}
        with _stage(prov, "parse_orient_validate"):
            n_grid_fail = 0
            for f in files:
                try:
                    grid = _load_grid(f.path, f.stem, cache, config)
                except ReconstructionError as exc:
                    logger.error("Parse/orient failed for %s: %s", f.stem, exc)
                    registry.add(f, None)
                    n_grid_fail += 1
                    continue
                rep = grid_validator.validate_grid(grid, config)
                registry.add(f, grid)
                if rep.passed:
                    grids[f.stem] = grid
                else:
                    n_grid_fail += 1
            registry.write_csv(config.reports_dir() / "surface_metadata.csv")
            registry.write_json(config.reports_dir() / "surface_metadata.json")
            summary.append(f"Grids valid: {len(grids)}  (failed/rejected: {n_grid_fail})")

        # --- Stage 5: topology recovery + validation ---
        with _stage(prov, "topology"):
            topo = topology_analyser.analyse(files, grids, config)
            diagnostics.write_json(topo.summary, config.reports_dir() / "topology_summary.json")
            topo_rep = topology_validator.validate_topology(topo)
            diagnostics.write_json(topo_rep, config.reports_dir() / "topology_validation.json")
            summary.append(
                f"Topology: components={topo.summary['n_components']}/13 "
                f"seam_matches={topo.summary['n_seam_matches']} "
                f"graph_connected={topo_rep.connected}"
            )

        # --- Stages 6-10a: per-component geometry (engine body) ---
        with _stage(prov, "component_geometry"):
            all_fits = []
            all_faces = []
            component_shells = []
            for comp_key in expected_topology.ENGINE_BODY_COMPONENTS:
                stems = sorted(topo.components.get(comp_key, []))
                comp_faces = []
                for stem in stems:
                    if stem not in grids:
                        logger.warning("Skipping %s (no valid grid)", stem)
                        continue
                    fit = bspline_builder.fit_surface(grids[stem], config)
                    all_fits.append(fit)
                    fr = face_builder.build_face(fit, config)
                    all_faces.append(fr)
                    comp_faces.append(fr.face)
                if comp_faces:
                    res = shell_builder.sew_progressive(comp_faces, config, comp_key)
                    component_shells.append(shell_builder.heal_shell(res.shape))
            geom_rep = geometry_validator.validate_geometry(
                all_faces, all_fits, config.area_deviation_pass_pct
            )
            diagnostics.write_json(geom_rep, config.reports_dir() / "geometry_validation.json")
            summary.append(
                f"Engine-body faces: {geom_rep.n_valid_faces}/{geom_rep.n_faces} valid, "
                f"max area dev {geom_rep.max_area_deviation_pct:.3f}%"
            )

        # --- Stage 6b: pylon geometry (fairing -> assembly; cut/trim -> aux) ---
        pylon_fairing_faces: list = []
        pylon_aux_faces: list = []
        if config.include_pylon:
            with _stage(prov, "pylon_geometry"):
                pylon_stems = sorted(
                    stem
                    for stem in grids
                    if files_by_stem[stem].surface_class is SurfaceClass.PYLON
                )
                for stem in pylon_stems:
                    is_aux = expected_topology.is_pylon_aux(stem)
                    if is_aux and not config.include_pylon_aux:
                        continue
                    try:
                        grid = downsampling.downsample_to_cap(grids[stem], config.pylon_fit_cap)
                        face = face_builder.build_face(
                            bspline_builder.fit_surface(grid, config), config
                        ).face
                    except ReconstructionError as exc:
                        logger.warning("Pylon surface %s failed: %s", stem, exc)
                        continue
                    (pylon_aux_faces if is_aux else pylon_fairing_faces).append(face)
                summary.append(
                    f"Pylon faces: fairing={len(pylon_fairing_faces)} "
                    f"aux(cut/trim)={len(pylon_aux_faces)}"
                )

        # --- Stage 7: expected shared seams (diagnostic) ---
        with _stage(prov, "shared_edges"):
            expected_seams = shared_edge_builder.expected_shared_seams(topo.seam_matches)
            diagnostics.write_json(
                [vars(s) for s in expected_seams],
                config.reports_dir() / "expected_shared_seams.json",
            )

        # --- Stage 10b: watertight engine assembly (body + pylon fairing) ---
        with _stage(prov, "engine_assembly"):
            assembly_faces = [fr.face for fr in all_faces] + pylon_fairing_faces
            assembled = shell_builder.sew_progressive(
                assembly_faces, config, "RB3135_engine_assembly"
            )
            engine_assembly = shell_builder.heal_shell(assembled.shape)
            summary.append(
                f"Engine assembly: faces={assembled.n_faces} shells={assembled.n_shells} "
                f"shared={assembled.n_shared_edges} free={assembled.n_free_edges} "
                f"unsewn_pairs={assembled.n_unsewn_pairs} (sew tol={assembled.tolerance:g})"
            )

        # --- Stage 11: watertight (manifold) report on the assembly ---
        with _stage(prov, "watertight"):
            wt = watertight_validator.validate_watertight(
                engine_assembly, config, expected_seams=len(expected_seams)
            )
            diagnostics.write_json(wt, config.reports_dir() / "watertight_report.json")
            summary.append(
                f"Watertight: PASS={wt.passed} shells={assembled.n_shells} "
                f"shared_edges={wt.n_shared_edges} free_edges={wt.n_free_edges}"
            )

        # --- Stage 12a: pylon auxiliary (cut/trim) node ---
        pylon_aux = None
        if pylon_aux_faces:
            with _stage(prov, "pylon_aux"):
                aux_res = shell_builder.sew_progressive(pylon_aux_faces, config, "RB3135_pylon_aux")
                pylon_aux = shell_builder.heal_shell(aux_res.shape)
                summary.append(f"Pylon aux (cut/trim) node: {len(pylon_aux_faces)} faces")

        # --- Stage 12b: CFD density zones node ---
        density_compound = None
        if config.include_density_zones:
            with _stage(prov, "density_zones"):
                density_compound = _build_density_compound(
                    files_by_stem,
                    grids,
                    config,
                    bspline_builder,
                    face_builder,
                    shell_builder,
                    solid_builder,
                )
                summary.append("CFD density zones: reconstructed as separate node")

        # --- optional component compound (off by default; avoids duplicate geometry) ---
        component_compound = (
            solid_builder.make_compound(component_shells)
            if config.include_component_compound
            else None
        )

        # --- Stage 13: STEP export (watertight assembly + auxiliary nodes) ---
        with _stage(prov, "export"):
            nodes = [
                ("RB3135_Engine_Assembly", engine_assembly),
                ("RB3135_Pylon_Aux", pylon_aux),
                ("RB3135_CFD_Density_Zones", density_compound),
                ("RB3135_Engine_Components", component_compound),
            ]
            result = step_exporter.export_step(config.step_path(), nodes)
            summary.append(
                f"STEP written: {result.path} (schema {result.schema}, nodes: {result.nodes})"
            )

        prov.finalize("SUCCESS")
        summary.append("OUTCOME: SUCCESS")
        _finish(prov, summary, config)
        logger.info("Pipeline completed successfully -> %s", config.step_path())
        return 0

    except WatertightnessError as exc:
        prov.finalize("FAILED_WATERTIGHT")
        summary.append(f"OUTCOME: FAILED (watertight) - {exc}")
        summary.append("No STEP file written (hard requirement not met).")
        _finish(prov, summary, config)
        logger.error("Pipeline hard-failed on watertight gate: %s", exc)
        return 2
    except ReconstructionError as exc:
        prov.finalize("FAILED")
        summary.append(f"OUTCOME: FAILED - {exc}")
        _finish(prov, summary, config)
        logger.exception("Pipeline failed: %s", exc)
        return 1


def _build_density_compound(
    files_by_stem, grids, config, bspline_builder, face_builder, shell_builder, solid_builder
):
    """Reconstruct CFD density zones, grouped by zone, into a single compound."""
    zones: dict[str, list[str]] = {}
    for stem, f in files_by_stem.items():
        if f.surface_class is SurfaceClass.CFD_DENSITY and stem in grids:
            zones.setdefault(_density_zone_key(stem), []).append(stem)

    shells = []
    for zone, stems in sorted(zones.items()):
        faces = []
        for stem in sorted(stems):
            try:
                fit = bspline_builder.fit_surface(grids[stem], config)
                faces.append(face_builder.build_face(fit, config).face)
            except ReconstructionError as exc:
                logger.warning("Density surface %s failed: %s", stem, exc)
        if not faces:
            continue
        res = shell_builder.sew_progressive(faces, config, f"density:{zone}")
        shells.append(shell_builder.heal_shell(res.shape))
    logger.info("Reconstructed %d CFD density zone shell(s)", len(shells))
    return solid_builder.make_compound(shells)


def _finish(prov: Provenance, summary: list[str], config: Config) -> None:
    """Persist provenance and the text summary."""
    prov.write(config.reports_dir() / "provenance.json")
    diagnostics.write_summary(summary, config.reports_dir() / "pipeline_summary.txt")
    for line in summary:
        logger.info("SUMMARY | %s", line)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Reconstruct a STEP model of the RB3135 free-flying engine from FPD files."
    )
    parser.add_argument("--fpd-dir", type=Path, help="Directory of .fpd files")
    parser.add_argument("--output-dir", type=Path, help="Output directory")
    parser.add_argument(
        "--with-density",
        action="store_true",
        help="Add the CFD density-zone node (large CFD-domain cylinders)",
    )
    parser.add_argument(
        "--no-pylon", action="store_true", help="Exclude the pylon from the assembly"
    )
    parser.add_argument(
        "--with-pylon-aux",
        action="store_true",
        help="Add the pylon cut/trim (construction) node (large stray planes)",
    )
    parser.add_argument(
        "--with-components",
        action="store_true",
        help="Also add the per-component compound node (duplicates engine geometry)",
    )
    parser.add_argument("--downsample", action="store_true", help="Enable grid downsampling")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Hard-fail (no STEP) if the engine assembly is not watertight/manifold",
    )
    args = parser.parse_args(argv)

    overrides: dict[str, object] = {}
    if args.fpd_dir:
        overrides["fpd_dir"] = args.fpd_dir
    if args.output_dir:
        overrides["output_dir"] = args.output_dir
    if args.with_density:
        overrides["include_density_zones"] = True
    if args.no_pylon:
        overrides["include_pylon"] = False
    if args.with_pylon_aux:
        overrides["include_pylon_aux"] = True
    if args.with_components:
        overrides["include_component_compound"] = True
    if args.downsample:
        overrides["downsample"] = True
    if args.strict:
        overrides["strict_watertight"] = True

    config: Config = load_config(**overrides)
    return run(config)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
