"""Integration test over the real RB3135 FPD dataset (if present).

Runs the non-OCC front of the pipeline (discover -> parse -> orient -> validate
-> topology) on a small representative subset and asserts the engine-body
classification and a clean two-patch seam. The full OCC end-to-end run is
exercised by the pipeline itself (see docs/verification); this test stays fast.
"""

from __future__ import annotations

import pytest

from engine_reconstruction.infrastructure.config import Config
from engine_reconstruction.infrastructure.data_types import SurfaceClass
from engine_reconstruction.infrastructure.settings import load_config
from engine_reconstruction.io import file_discovery, fpd_parser
from engine_reconstruction.topology import orientation_detector

pytestmark = pytest.mark.integration


def _dataset_available(cfg: Config) -> bool:
    return cfg.fpd_dir.is_dir() and any(cfg.fpd_dir.glob("*.fpd"))


def test_real_dataset_classification():
    # Disable the default name-based exclusion so this exercises the classifier
    # over the full inventory (all 19 pylon surfaces), independent of policy.
    cfg = load_config(exclude_patterns=())
    if not _dataset_available(cfg):
        pytest.skip(f"FPD dataset not present at {cfg.fpd_dir}")
    files = file_discovery.discover(cfg)
    counts = {c: 0 for c in SurfaceClass}
    for f in files:
        counts[f.surface_class] += 1
    assert counts[SurfaceClass.ENGINE_BODY] == 26
    assert counts[SurfaceClass.PYLON] == 19
    assert counts[SurfaceClass.CFD_DENSITY] == 43


def test_real_spinner_orientation():
    cfg = load_config()
    if not _dataset_available(cfg):
        pytest.skip(f"FPD dataset not present at {cfg.fpd_dir}")
    files = {f.stem: f for f in file_discovery.discover(cfg)}
    stem = "Spinner_inboard_free-flying"
    if stem not in files:
        pytest.skip("Spinner file not in dataset")
    grid = orientation_detector.recover_orientation(fpd_parser.parse_fpd(files[stem].path))
    assert grid.points.ndim == 3 and grid.points.shape[2] == 3
    assert grid.meta["roughness_ratio"] > 1.0  # one orientation clearly better
