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
