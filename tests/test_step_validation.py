"""Validate the exported STEP against the FPD inputs.

Two layers:

1. **Inventory accounting** (fast, no OpenCASCADE): the set of surfaces the
   pipeline reconstructs is exactly the selected configuration's files *minus*
   the name-excluded ones — i.e. every FPD file is used except configuration-
   and pattern-excluded ones. Runs for both ``installed`` and ``uninstalled``.

2. **End-to-end STEP validation** (OpenCASCADE + real data): reconstruct into a
   temp dir, read the written STEP back, and assert it is a valid, watertight
   CAD assembly whose face count equals the engine-body + pylon-fairing surfaces
   that should have been used — and that the excluded heatshield is absent.

   The reconstruction is slow (full B-spline fitting of the pylon), so it is
   gated behind ``RB3135_RUN_SLOW=1`` to keep the default ``pytest`` run quick::

       RB3135_RUN_SLOW=1 conda run -n rb3135 python -m pytest tests/test_step_validation.py
"""

from __future__ import annotations

import os

import pytest

from conftest import requires_occ
from engine_reconstruction.infrastructure.config import Config
from engine_reconstruction.infrastructure.data_types import SurfaceClass
from engine_reconstruction.infrastructure.settings import load_config
from engine_reconstruction.io import file_discovery
from engine_reconstruction.topology import expected_topology

pytestmark = pytest.mark.integration

run_slow = pytest.mark.skipif(
    os.environ.get("RB3135_RUN_SLOW", "").strip().lower() not in {"1", "true", "yes", "on"},
    reason="slow end-to-end reconstruction; set RB3135_RUN_SLOW=1 to enable",
)


def _dataset_available(cfg: Config) -> bool:
    return cfg.fpd_dir.is_dir() and any(cfg.fpd_dir.glob("*.fpd"))


def _files_in_configuration(cfg: Config) -> list:
    """The .fpd stems belonging to cfg.configuration (untagged files count too)."""
    wanted = cfg.configuration.strip().lower()
    return [
        p
        for p in sorted(cfg.fpd_dir.glob("*.fpd"))
        if (file_discovery.config_tag(p.stem) or wanted) == wanted
    ]


# --------------------------------------------------------------------------- #
# 1. Inventory accounting (fast, no OCC)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("configuration", ["installed", "uninstalled"])
def test_discovery_uses_all_files_except_excluded(configuration):
    cfg = load_config(configuration=configuration)
    if not _dataset_available(cfg):
        pytest.skip(f"FPD dataset not present at {cfg.fpd_dir}")

    in_config = _files_in_configuration(cfg)
    excluded = [
        p for p in in_config if file_discovery.matches_exclude(p.stem, cfg.exclude_patterns)
    ]
    expected = {p.stem for p in in_config} - {p.stem for p in excluded}

    discovered = {f.stem for f in file_discovery.discover(cfg)}

    # Every in-configuration file is used except the pattern-excluded ones.
    assert discovered == expected
    # The default exclusion actually dropped the heatshield (and nothing leaked).
    assert excluded, "expected the default exclusion to drop the heatshield files"
    assert not any(file_discovery.matches_exclude(s, cfg.exclude_patterns) for s in discovered)
    # No file from the other configuration slipped in.
    other = "uninstalled" if configuration == "installed" else "installed"
    assert not any(file_discovery.config_tag(s) == other for s in discovered)


def test_excluded_files_are_the_heatshield(configuration="uninstalled"):
    cfg = load_config(configuration=configuration)
    if not _dataset_available(cfg):
        pytest.skip(f"FPD dataset not present at {cfg.fpd_dir}")
    excluded = sorted(
        p.stem
        for p in _files_in_configuration(cfg)
        if file_discovery.matches_exclude(p.stem, cfg.exclude_patterns)
    )
    assert excluded
    assert all("heatshield" in s.lower() for s in excluded)


# --------------------------------------------------------------------------- #
# 2. End-to-end STEP validation (OCC + real data; slow)
# --------------------------------------------------------------------------- #
def _count(shape, kind) -> int:
    from OCC.Core.TopExp import TopExp_Explorer

    exp = TopExp_Explorer(shape, kind)
    n = 0
    while exp.More():
        n += 1
        exp.Next()
    return n


@pytest.fixture(scope="module")
def reconstructed(tmp_path_factory):
    """Run the full default pipeline once into a temp dir; yield (cfg, step_path)."""
    cfg = load_config(output_dir=tmp_path_factory.mktemp("step_out"))
    if not _dataset_available(cfg):
        pytest.skip(f"FPD dataset not present at {cfg.fpd_dir}")
    from engine_reconstruction.pipeline import engine_pipeline

    assert engine_pipeline.run(cfg) == 0, "pipeline did not complete successfully"
    return cfg, cfg.step_path()


@run_slow
@requires_occ
def test_step_file_written_and_readable(reconstructed):
    _, step_path = reconstructed
    assert step_path.exists() and step_path.stat().st_size > 0

    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_Reader

    reader = STEPControl_Reader()
    assert reader.ReadFile(str(step_path)) == IFSelect_RetDone
    assert reader.TransferRoots() > 0
    assert not reader.OneShape().IsNull()


@run_slow
@requires_occ
def test_step_is_single_watertight_assembly_using_expected_surfaces(reconstructed):
    cfg, step_path = reconstructed

    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SHELL
    from OCC.Core.TopoDS import TopoDS_Iterator

    from engine_reconstruction.validation import watertight_validator

    reader = STEPControl_Reader()
    reader.ReadFile(str(step_path))
    reader.TransferRoots()

    # Exactly one node: the engine assembly (density/pylon-aux are off by default).
    nodes = []
    it = TopoDS_Iterator(reader.OneShape())
    while it.More():
        nodes.append(it.Value())
        it.Next()
    assert len(nodes) == 1
    assembly = nodes[0]

    # Face count must equal the engine-body + pylon-fairing surfaces that were
    # discovered (heatshield excluded) — i.e. the STEP uses exactly those files.
    files = file_discovery.discover(cfg)
    n_engine = sum(f.surface_class is SurfaceClass.ENGINE_BODY for f in files)
    n_fairing = sum(
        f.surface_class is SurfaceClass.PYLON and expected_topology.is_pylon_fairing(f.stem)
        for f in files
    )
    assert _count(assembly, TopAbs_FACE) == n_engine + n_fairing
    assert _count(assembly, TopAbs_SHELL) >= 1

    # No discovered file is a heatshield surface (it was excluded by default).
    assert not any("heatshield" in f.stem.lower() for f in files)

    # The assembly satisfies the watertight (no coincident free-edge) gate.
    report = watertight_validator.validate_watertight(assembly, cfg)
    assert report.passed
    assert report.n_free_edges >= 0
    assert report.n_shared_edges > 0
