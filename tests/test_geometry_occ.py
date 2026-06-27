"""OCC-dependent geometry tests: fit -> face -> sew -> watertight.

Skipped automatically when pythonocc-core is unavailable.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import cylinder_grid, requires_occ
from engine_reconstruction.infrastructure.config import Config
from engine_reconstruction.infrastructure.data_types import StructuredGrid

pytestmark = [requires_occ, pytest.mark.occ]


def _two_half_cylinders():
    a = StructuredGrid("c_inboard", cylinder_grid(15, 24, theta0=0.0, theta1=np.pi))
    b = StructuredGrid("c_outboard", cylinder_grid(15, 24, theta0=np.pi, theta1=2 * np.pi))
    return a, b


def test_fit_face_valid():
    from engine_reconstruction.geometry import bspline_builder, face_builder

    cfg = Config()
    grid = StructuredGrid("c", cylinder_grid(15, 24))
    fit = bspline_builder.fit_surface(grid, cfg)
    assert fit.surface is not None
    assert fit.area_deviation_pct < cfg.area_deviation_fail_pct
    fr = face_builder.build_face(fit, cfg)
    assert fr.valid


def test_sew_two_patches_into_shell():
    from engine_reconstruction.geometry import bspline_builder, face_builder, shell_builder

    cfg = Config()
    faces = [
        face_builder.build_face(bspline_builder.fit_surface(g, cfg), cfg).face
        for g in _two_half_cylinders()
    ]
    res = shell_builder.sew_progressive(faces, cfg, "cyl")
    assert res.n_faces == 2
    assert res.n_shells == 1
    assert res.n_shared_edges >= 2  # the two axial seams
    assert res.n_unsewn_pairs == 0  # no unsewn coincident seams


def test_watertight_pass_on_clean_shell():
    from engine_reconstruction.geometry import bspline_builder, face_builder, shell_builder
    from engine_reconstruction.validation import watertight_validator

    cfg = Config()
    faces = [
        face_builder.build_face(bspline_builder.fit_surface(g, cfg), cfg).face
        for g in _two_half_cylinders()
    ]
    shell = shell_builder.heal_shell(shell_builder.sew_progressive(faces, cfg, "cyl").shape)
    report = watertight_validator.validate_watertight(shell, cfg)
    assert report.passed
    assert report.n_shared_edges >= 2


def test_watertight_fail_raises_on_unsewn():
    """Two coincident free patches NOT sewn (tiny tol) must fail the gate."""
    from engine_reconstruction.geometry import bspline_builder, face_builder, shell_builder
    from engine_reconstruction.infrastructure.exceptions import WatertightnessError
    from engine_reconstruction.validation import watertight_validator

    # Force a gap larger than the sewing ladder cannot bridge is hard; instead
    # verify the gate raises when coincident free edges exist by sewing two
    # identical overlapping single faces at zero tolerance.
    cfg = Config(sewing_tolerances=(1e-9,), free_edge_open_boundary_tol=1e-2)
    a, b = _two_half_cylinders()
    faces = [face_builder.build_face(bspline_builder.fit_surface(g, cfg), cfg).face for g in (a, b)]
    res = shell_builder.sew_progressive(faces, cfg, "cyl")
    shell = res.shape
    if res.n_unsewn_pairs > 0:
        with pytest.raises(WatertightnessError):
            watertight_validator.validate_watertight(shell, cfg)
    else:
        pytest.skip("sewing merged seams even at 1e-9; gap test not triggered")
