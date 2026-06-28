"""End-to-end topology-correctness checks over the real RB3135 dataset.

Verifies that topology recovery reproduces the engine's known skeleton:

* all 13 axisymmetric engine-body components are present,
* every engine-body surface maps to a skeleton component (prefix match),
* each component is the expected inboard/outboard patch pair, and
* their adjacency graph forms a *single connected group* — the prerequisite
  for sewing one merged watertight shell.

Pure NumPy/SciPy: no OpenCASCADE required. Skips when the dataset is absent, so
it is safe to run anywhere. Orients only the engine-body grids (adjacency is
computed over those), keeping the run fast.
"""

from __future__ import annotations

import pytest

from engine_reconstruction.infrastructure.config import Config
from engine_reconstruction.infrastructure.data_types import StructuredGrid, SurfaceClass
from engine_reconstruction.infrastructure.settings import load_config
from engine_reconstruction.io import file_discovery, fpd_parser
from engine_reconstruction.topology import (
    expected_topology,
    orientation_detector,
    topology_analyser,
)
from engine_reconstruction.validation import topology_validator

pytestmark = pytest.mark.integration


def _dataset_available(cfg: Config) -> bool:
    return cfg.fpd_dir.is_dir() and any(cfg.fpd_dir.glob("*.fpd"))


@pytest.fixture(scope="module")
def topo():
    """Discover + orient engine-body grids + recover topology, once per module."""
    cfg = load_config()
    if not _dataset_available(cfg):
        pytest.skip(f"FPD dataset not present at {cfg.fpd_dir}")
    files = file_discovery.discover(cfg)
    grids: dict[str, StructuredGrid] = {
        f.stem: orientation_detector.recover_orientation(fpd_parser.parse_fpd(f.path))
        for f in files
        if f.surface_class is SurfaceClass.ENGINE_BODY
    }
    result = topology_analyser.analyse(files, grids, cfg)
    return cfg, files, result


def test_every_engine_body_surface_maps_to_a_skeleton_component(topo):
    _, files, _ = topo
    unmatched = [
        f.stem
        for f in files
        if f.surface_class is SurfaceClass.ENGINE_BODY
        and expected_topology.match_engine_component(f.stem) is None
    ]
    assert not unmatched, f"engine-body surfaces with no skeleton component: {unmatched}"


def test_all_thirteen_components_present(topo):
    _, _, result = topo
    assert set(result.components) == set(expected_topology.ENGINE_BODY_COMPONENTS)
    assert result.summary["n_components"] == 13
    assert result.summary["missing_components"] == 0


def test_each_component_is_an_inboard_outboard_pair(topo):
    _, _, result = topo
    for comp, stems in result.components.items():
        assert len(stems) == 2, f"{comp}: expected an inboard+outboard pair, got {stems}"
    # 13 components x 2 patches = 26 engine-body surfaces.
    assert result.summary["n_engine_body"] == 2 * len(expected_topology.ENGINE_BODY_COMPONENTS)


def test_adjacency_graph_is_one_connected_group(topo):
    _, _, result = topo
    rep = topology_validator.validate_topology(result)
    assert rep.passed
    assert rep.connected
    assert rep.n_graph_components == 1
    # The single group must span every engine-body surface (none isolated).
    assert rep.largest_component_size == result.summary["n_engine_body"]
    assert not rep.isolated_surfaces


def test_seams_are_detected_and_geometrically_tight(topo):
    cfg, _, result = topo
    # At least the two intra-component circumferential seams per 2-patch component.
    assert result.summary["n_seam_matches"] >= 2 * len(expected_topology.ENGINE_BODY_COMPONENTS)
    # Every detected coincidence must be within the matcher's RMS tolerance.
    assert result.seam_matches
    assert all(m.rms <= cfg.seam_match_rms_tol for m in result.seam_matches)


def test_no_csv_override_conflicts_by_default(topo):
    _, _, result = topo
    # Default config does not apply the CSV override, so classification is purely
    # name-derived and must not report conflicts.
    assert result.summary["override_conflicts"] == 0
