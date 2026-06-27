"""Stage 2 — parse FPD files into raw point arrays.

Supports several structured-grid formats behind one entry point
(:func:`parse_fpd`); the format is auto-detected from file content:

* **ICEM** (native to this dataset): line 1 = ``ni nj``; then ``ni*nj`` lines of
  ``X Y Z`` in file order (i-fastest). No ZONE/VARIABLES header.
* **Tecplot POINT**: ``ZONE`` header with ``I=`` / ``J=`` and ``F=POINT``;
  one ``X Y Z`` per line.
* **Tecplot BLOCK**: ``F=BLOCK``; all X, then all Y, then all Z.
* **PLOT3D (ASCII, single grid)**: line 1 = number of blocks (optional), then
  ``ni nj [nk]`` and X-block, Y-block, Z-block.

The parser only *decodes* — it returns a :class:`ParsedFpd` in file order. The
orientation stage selects the correct reshape into a canonical grid.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ..infrastructure.data_types import FpdFormat, ParsedFpd
from ..infrastructure.exceptions import FpdParseError, UnsupportedFormatError
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)

_INT_RE = re.compile(r"^\s*\d+(\s+\d+){1,2}\s*$")
_ZONE_RE = re.compile(r"\bI\s*=\s*(\d+).*?\bJ\s*=\s*(\d+)", re.IGNORECASE | re.DOTALL)


def detect_format(path: Path) -> FpdFormat:
    """Detect the FPD file format by inspecting the first few lines."""
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        head = [fh.readline() for _ in range(6)]
    text = "".join(head)
    upper = text.upper()

    if "ZONE" in upper or "VARIABLES" in upper or "TITLE" in upper:
        if "F=BLOCK" in upper.replace(" ", "") or "FORMAT=BLOCK" in upper.replace(" ", ""):
            return FpdFormat.TECPLOT_BLOCK
        return FpdFormat.TECPLOT_POINT

    first = head[0].strip()
    # ICEM: first line is exactly two integers.
    if re.fullmatch(r"\d+\s+\d+", first):
        return FpdFormat.ICEM
    # PLOT3D: first line is a single int (nblocks) or three ints (ni nj nk).
    if re.fullmatch(r"\d+", first) or re.fullmatch(r"\d+\s+\d+\s+\d+", first):
        return FpdFormat.PLOT3D
    raise UnsupportedFormatError(f"Cannot detect FPD format for {path.name!r}")


def _load_floats(tokens: list[str]) -> np.ndarray:
    try:
        return np.asarray([float(t) for t in tokens], dtype=np.float64)
    except ValueError as exc:  # pragma: no cover - defensive
        raise FpdParseError(f"Non-numeric token encountered: {exc}") from exc


def _parse_icem(path: Path) -> ParsedFpd:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        first = fh.readline().split()
        ni, nj = int(first[0]), int(first[1])
        data = np.loadtxt(fh, dtype=np.float64)
    coords = data.reshape(-1, 3)
    expected = ni * nj
    if coords.shape[0] != expected:
        raise FpdParseError(
            f"{path.name}: header says {ni}x{nj}={expected} points "
            f"but file has {coords.shape[0]}"
        )
    return ParsedFpd(path.stem, coords, ni, nj, path, FpdFormat.ICEM)


def _parse_tecplot_point(path: Path) -> ParsedFpd:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = _ZONE_RE.search(text)
    if not m:
        raise FpdParseError(f"{path.name}: Tecplot POINT zone missing I=/J=")
    ni, nj = int(m.group(1)), int(m.group(2))
    rows: list[list[float]] = []
    for line in text.splitlines():
        toks = line.split()
        if len(toks) >= 3:
            try:
                rows.append([float(toks[0]), float(toks[1]), float(toks[2])])
            except ValueError:
                continue
    coords = np.asarray(rows, dtype=np.float64)[: ni * nj]
    if coords.shape[0] != ni * nj:
        raise FpdParseError(f"{path.name}: expected {ni * nj} POINT rows, got {coords.shape[0]}")
    return ParsedFpd(path.stem, coords, ni, nj, path, FpdFormat.TECPLOT_POINT)


def _parse_tecplot_block(path: Path) -> ParsedFpd:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = _ZONE_RE.search(text)
    if not m:
        raise FpdParseError(f"{path.name}: Tecplot BLOCK zone missing I=/J=")
    ni, nj = int(m.group(1)), int(m.group(2))
    n = ni * nj
    nums: list[float] = []
    started = False
    for line in text.splitlines():
        if not started:
            if "ZONE" in line.upper():
                started = True
            continue
        for tok in line.split():
            try:
                nums.append(float(tok))
            except ValueError:
                pass
    arr = np.asarray(nums[: 3 * n], dtype=np.float64)
    if arr.shape[0] != 3 * n:
        raise FpdParseError(f"{path.name}: expected {3 * n} BLOCK values, got {arr.shape[0]}")
    x, y, z = arr[:n], arr[n : 2 * n], arr[2 * n :]
    coords = np.column_stack([x, y, z])
    return ParsedFpd(path.stem, coords, ni, nj, path, FpdFormat.TECPLOT_BLOCK)


def _parse_plot3d(path: Path) -> ParsedFpd:
    tokens = path.read_text(encoding="utf-8", errors="replace").split()
    idx = 0
    # Optional leading nblocks (a lone integer that is not a dims triple).
    has_nblocks = bool(re.fullmatch(r"\d+", tokens[0])) and not _looks_like_dims(tokens[:3])
    if has_nblocks:
        idx = 1
    ni = int(tokens[idx])
    nj = int(tokens[idx + 1])
    nk = 1
    # Detect optional nk.
    if idx + 2 < len(tokens) and re.fullmatch(r"\d+", tokens[idx + 2]):
        maybe_nk = int(tokens[idx + 2])
        if maybe_nk in (1,) and ni * nj * maybe_nk * 3 + (idx + 3) <= len(tokens):
            nk = maybe_nk
            idx += 3
        else:
            idx += 2
    else:
        idx += 2
    n = ni * nj * nk
    vals = _load_floats(tokens[idx : idx + 3 * n])
    if vals.shape[0] != 3 * n:
        raise FpdParseError(f"{path.name}: expected {3 * n} PLOT3D values, got {vals.shape[0]}")
    x, y, z = vals[:n], vals[n : 2 * n], vals[2 * n :]
    coords = np.column_stack([x, y, z])
    return ParsedFpd(path.stem, coords, ni, nj * nk, path, FpdFormat.PLOT3D)


def _looks_like_dims(tokens: list[str]) -> bool:
    return len(tokens) == 3 and all(re.fullmatch(r"\d+", t) for t in tokens)


_PARSERS = {
    FpdFormat.ICEM: _parse_icem,
    FpdFormat.TECPLOT_POINT: _parse_tecplot_point,
    FpdFormat.TECPLOT_BLOCK: _parse_tecplot_block,
    FpdFormat.PLOT3D: _parse_plot3d,
}


def parse_fpd(path: Path, fmt: FpdFormat | None = None) -> ParsedFpd:
    """Parse an FPD file into a :class:`ParsedFpd` (points in file order).

    Args:
        path: Path to the FPD file.
        fmt: Optional explicit format; auto-detected when ``None``.

    Returns:
        Decoded :class:`ParsedFpd`.

    Raises:
        FpdParseError: On any decode or consistency failure.
    """
    fmt = fmt or detect_format(path)
    parser = _PARSERS.get(fmt)
    if parser is None:  # pragma: no cover - defensive
        raise UnsupportedFormatError(f"No parser for format {fmt}")
    parsed = parser(path)
    logger.debug(
        "Parsed %s as %s: %dx%d = %d pts",
        path.name,
        fmt.value,
        parsed.ni,
        parsed.nj,
        parsed.n_points,
    )
    return parsed
