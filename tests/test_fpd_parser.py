"""Tests for FPD format detection and parsing."""

from __future__ import annotations

import numpy as np
import pytest

from engine_reconstruction.infrastructure.data_types import FpdFormat
from engine_reconstruction.infrastructure.exceptions import FpdParseError
from engine_reconstruction.io import fpd_parser


def test_detect_icem(icem_file):
    assert fpd_parser.detect_format(icem_file) is FpdFormat.ICEM


def test_parse_icem_counts(icem_file):
    parsed = fpd_parser.parse_fpd(icem_file)
    assert parsed.source_format is FpdFormat.ICEM
    assert (parsed.ni, parsed.nj) == (3, 5)
    assert parsed.coords.shape == (15, 3)


def test_parse_icem_bad_count(tmp_path):
    p = tmp_path / "bad.fpd"
    p.write_text("3 5\n0 0 0\n1 1 1\n")  # header says 15 points, only 2 present
    with pytest.raises(FpdParseError):
        fpd_parser.parse_fpd(p)


def test_parse_tecplot_point(tmp_path):
    p = tmp_path / "tec.fpd"
    lines = ['VARIABLES = "X" "Y" "Z"', "ZONE I=2, J=2, F=POINT"]
    pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
    lines += [f"{x} {y} {z}" for x, y, z in pts]
    p.write_text("\n".join(lines))
    assert fpd_parser.detect_format(p) is FpdFormat.TECPLOT_POINT
    parsed = fpd_parser.parse_fpd(p)
    assert parsed.coords.shape == (4, 3)
    np.testing.assert_allclose(parsed.coords[-1], (1, 1, 0))


def test_parse_tecplot_block(tmp_path):
    p = tmp_path / "tecb.fpd"
    lines = ["VARIABLES = X Y Z", "ZONE I=2, J=2, F=BLOCK"]
    lines += ["0 1 0 1", "0 0 1 1", "0 0 0 0"]  # X..., Y..., Z...
    p.write_text("\n".join(lines))
    assert fpd_parser.detect_format(p) is FpdFormat.TECPLOT_BLOCK
    parsed = fpd_parser.parse_fpd(p)
    assert parsed.coords.shape == (4, 3)
    np.testing.assert_allclose(parsed.coords[:, 0], (0, 1, 0, 1))
