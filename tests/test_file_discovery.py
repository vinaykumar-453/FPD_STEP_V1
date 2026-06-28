"""Tests for name-based FPD classification and discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine_reconstruction.infrastructure.config import Config
from engine_reconstruction.infrastructure.data_types import SurfaceClass
from engine_reconstruction.infrastructure.exceptions import DiscoveryError
from engine_reconstruction.io import file_discovery


@pytest.mark.parametrize(
    "stem,expected_class,expected_system,expected_role",
    [
        ("Spinner_inboard_free-flying", SurfaceClass.ENGINE_BODY, "Intake", "inboard"),
        ("BP_nozzle_Blunt_TE_outboard_free-flying", SurfaceClass.ENGINE_BODY, "Bypass", "outboard"),
        ("CR_inner_inboard_free-flying", SurfaceClass.ENGINE_BODY, "Core", "inboard"),
        ("Nacelle_outboard_free-flying", SurfaceClass.ENGINE_BODY, "Nacelle", "outboard"),
        ("Pylon_upper_free-flying", SurfaceClass.PYLON, "Pylon", "surface"),
        (
            "Whole_engine_density_cylindrical_surface_free-flying",
            SurfaceClass.CFD_DENSITY,
            "CFD Auxiliary",
            "surface",
        ),
        (
            "Jet_density_1_cylindrical_base_upstream_free-flying",
            SurfaceClass.CFD_DENSITY,
            "CFD Auxiliary",
            "base_upstream",
        ),
    ],
)
def test_classify(stem, expected_class, expected_system, expected_role):
    f = file_discovery.classify(Path(f"/x/{stem}.fpd"))
    assert f.surface_class is expected_class
    assert f.system == expected_system
    assert f.role == expected_role


def test_discover_missing_dir(tmp_path):
    cfg = Config(fpd_dir=tmp_path / "nope")
    with pytest.raises(DiscoveryError):
        file_discovery.discover(cfg)


def test_discover_empty_dir(tmp_path):
    cfg = Config(fpd_dir=tmp_path)
    with pytest.raises(DiscoveryError):
        file_discovery.discover(cfg)


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("BP_inner_inboard_installed", "installed"),
        ("Spinner_outboard_uninstalled", "uninstalled"),
        ("Spinner_inboard_free-flying", None),
        ("Pylon_upper_installed", "installed"),
    ],
)
def test_config_tag(stem, expected):
    assert file_discovery.config_tag(stem) == expected


def test_classify_strips_installed_suffix():
    f = file_discovery.classify(Path("/x/BP_inner_inboard_installed.fpd"))
    assert f.surface_class is SurfaceClass.ENGINE_BODY
    assert f.system == "Bypass"
    assert f.role == "inboard"


def test_discover_configuration_filter(tmp_path):
    grid = "2 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n"
    for name in [
        "BP_inner_inboard_installed",
        "BP_inner_inboard_uninstalled",
        "Spinner_inboard_free-flying",  # untagged -> always kept
    ]:
        (tmp_path / f"{name}.fpd").write_text(grid)
    files = file_discovery.discover(Config(fpd_dir=tmp_path, configuration="installed"))
    stems = {f.stem for f in files}
    assert "BP_inner_inboard_installed" in stems
    assert "Spinner_inboard_free-flying" in stems
    assert "BP_inner_inboard_uninstalled" not in stems  # other configuration dropped


@pytest.mark.parametrize(
    "stem,patterns,expected",
    [
        # substring match (case-insensitive), no glob metachar
        ("Pylon_heatshield_body_TE_cutoff_uninstalled", ("Pylon_heatshield_body",), True),
        ("Pylon_heatshield_body_inlet_cutoff_uninstalled", ("heatshield",), True),
        ("Pylon_upper_uninstalled", ("Pylon_heatshield_body",), False),
        ("Nacelle_inboard_uninstalled", ("Pylon_heatshield_body",), False),
        # glob match
        ("Pylon_heatshield_body_TE_cutoff_uninstalled", ("*cutoff*",), True),
        ("CR_TE_inboard_uninstalled", ("*cutoff*",), False),
        ("BP_inner_inboard_uninstalled", ("BP_*_inboard_*",), True),
        # multiple patterns / empty + blank are ignored
        ("Nacelle_inboard_uninstalled", ("foo", "", "  ", "nacelle"), True),
        ("Nacelle_inboard_uninstalled", (), False),
    ],
)
def test_matches_exclude(stem, patterns, expected):
    assert file_discovery.matches_exclude(stem, patterns) is expected


def test_discover_exclude_drops_matching(tmp_path):
    grid = "2 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n"
    for name in [
        "Pylon_upper_free-flying",
        "Pylon_heatshield_body_surface_cutoff_free-flying",
        "Pylon_heatshield_body_TE_cutoff_free-flying",
        "Nacelle_inboard_free-flying",
    ]:
        (tmp_path / f"{name}.fpd").write_text(grid)
    cfg = Config(fpd_dir=tmp_path, exclude_patterns=("Pylon_heatshield_body",))
    stems = {f.stem for f in file_discovery.discover(cfg)}
    assert stems == {"Pylon_upper_free-flying", "Nacelle_inboard_free-flying"}


def test_discover_exclude_none_keeps_all(tmp_path):
    grid = "2 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n"
    for name in ["Pylon_heatshield_body_TE_cutoff_free-flying", "Nacelle_inboard_free-flying"]:
        (tmp_path / f"{name}.fpd").write_text(grid)
    cfg = Config(fpd_dir=tmp_path, exclude_patterns=())
    assert len(file_discovery.discover(cfg)) == 2


def test_discover_exclude_all_raises(tmp_path):
    grid = "2 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n"
    (tmp_path / "Pylon_heatshield_body_TE_cutoff_free-flying.fpd").write_text(grid)
    cfg = Config(fpd_dir=tmp_path, exclude_patterns=("heatshield",))
    with pytest.raises(DiscoveryError):
        file_discovery.discover(cfg)


def test_discover_counts(tmp_path):
    for name in [
        "Spinner_inboard_free-flying",
        "Pylon_upper_free-flying",
        "Whole_engine_density_cylindrical_surface_free-flying",
    ]:
        (tmp_path / f"{name}.fpd").write_text("2 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n")
    files = file_discovery.discover(Config(fpd_dir=tmp_path, expected_fpd_count=3))
    classes = {f.surface_class for f in files}
    assert classes == {SurfaceClass.ENGINE_BODY, SurfaceClass.PYLON, SurfaceClass.CFD_DENSITY}
