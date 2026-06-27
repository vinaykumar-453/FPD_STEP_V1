"""Tests for topology recovery: component keys, grouping, adjacency."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from conftest import cylinder_grid
from engine_reconstruction.infrastructure.config import Config
from engine_reconstruction.infrastructure.data_types import StructuredGrid
from engine_reconstruction.io import file_discovery
from engine_reconstruction.topology import neighbour_detector, topology_analyser
from engine_reconstruction.topology.topology_analyser import component_key


def test_component_key():
    assert component_key("Spinner_inboard_free-flying") == "Spinner"
    assert component_key("BP_nozzle_Blunt_TE_outboard_free-flying") == "BP_nozzle_Blunt_TE"
    assert component_key("CR_inner_inboard_free-flying") == "CR_inner"
    # installed/uninstalled configuration suffixes are stripped too
    assert component_key("BP_inner_inboard_installed") == "BP_inner"
    assert component_key("CR_nozzle_Blunt_TE_outboard_uninstalled") == "CR_nozzle_Blunt_TE"


def test_match_engine_component_prefix():
    from engine_reconstruction.topology import expected_topology as et

    assert et.match_engine_component("BP_inner_inboard_installed") == "BP_inner"
    assert et.match_engine_component("BP_inlet_outboard_uninstalled") == "BP_inlet"
    # longest-first: the nozzle TE must not collapse to a shorter prefix
    assert et.match_engine_component("CR_nozzle_Blunt_TE_inboard_installed") == "CR_nozzle_Blunt_TE"
    assert et.match_engine_component("Spinner_inboard_free-flying") == "Spinner"
    assert et.match_engine_component("Whatever_unknown_surface") is None


def test_neighbour_detection_finds_shared_seam():
    # Two half-cylinders sharing the theta=pi seam.
    a = StructuredGrid("a_inboard", cylinder_grid(theta0=0.0, theta1=np.pi))
    b = StructuredGrid("b_outboard", cylinder_grid(theta0=np.pi, theta1=2 * np.pi))
    matches = neighbour_detector.match_boundaries(a, b, Config())
    assert matches, "expected at least one coincident boundary (shared seam)"
    assert min(m.rms for m in matches) < 1e-6


def test_analyse_groups_components():
    files = [
        file_discovery.classify(Path("/x/Spinner_inboard_free-flying.fpd")),
        file_discovery.classify(Path("/x/Spinner_outboard_free-flying.fpd")),
        file_discovery.classify(
            Path("/x/Whole_engine_density_cylindrical_surface_free-flying.fpd")
        ),
    ]
    grids = {
        "Spinner_inboard_free-flying": StructuredGrid(
            "Spinner_inboard_free-flying", cylinder_grid(theta0=0.0, theta1=np.pi)
        ),
        "Spinner_outboard_free-flying": StructuredGrid(
            "Spinner_outboard_free-flying", cylinder_grid(theta0=np.pi, theta1=2 * np.pi)
        ),
    }
    result = topology_analyser.analyse(files, grids, Config(use_topology_csv_override=False))
    assert "Spinner" in result.components
    assert set(result.components["Spinner"]) == {
        "Spinner_inboard_free-flying",
        "Spinner_outboard_free-flying",
    }
    assert result.summary["n_cfd_density"] == 1
    assert result.summary["n_engine_body"] == 2
