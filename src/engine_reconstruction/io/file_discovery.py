"""Stage 1 — discover and classify FPD files.

Globs the FPD directory, validates the inventory (count, duplicates, naming),
and classifies each file by name into an engine-body / pylon / CFD-density
:class:`SurfaceClass` together with a component key, system, and role token.

Classification here is *name-based* and fast; the topology stage may later
refine or override it (geometry-based auto-derivation + optional CSV).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..infrastructure.config import Config
from ..infrastructure.data_types import FpdFile, SurfaceClass
from ..infrastructure.exceptions import DiscoveryError
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)

_FREE_FLYING_SUFFIX = re.compile(r"[_-]free[_-]flying$", re.IGNORECASE)
_ROLE_TOKENS = ("inboard", "outboard")

# System lookup by component-key prefix (engine body).
_SYSTEM_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("Spinner", "Intake"),
    ("Fan_face", "Intake"),
    ("Intake", "Intake"),
    ("Nacelle", "Nacelle"),
    ("BP_", "Bypass"),
    ("CR_", "Core"),
)


def _strip_suffix(stem: str) -> str:
    return _FREE_FLYING_SUFFIX.sub("", stem)


def classify(path: Path) -> FpdFile:
    """Classify a single FPD file from its name.

    Args:
        path: Path to a ``.fpd`` file.

    Returns:
        A populated :class:`FpdFile`.
    """
    stem = path.stem
    base = _strip_suffix(stem)
    lower = base.lower()

    # --- surface class ---
    if "density" in lower:
        surface_class = SurfaceClass.CFD_DENSITY
    elif lower.startswith("pylon"):
        surface_class = SurfaceClass.PYLON
    else:
        surface_class = SurfaceClass.ENGINE_BODY

    # --- role + component key ---
    role = "surface"
    component_key = base
    for token in _ROLE_TOKENS:
        if lower.endswith("_" + token):
            role = token
            component_key = base[: -(len(token) + 1)]
            break
    else:
        # density / pylon roles: take trailing descriptor after last grouping word
        m = re.search(r"(base_[a-z]+|surface|cap|top|bottom|upstream|downstream)$", lower)
        if m:
            role = m.group(1)

    # --- system ---
    system = "Unknown"
    if surface_class is SurfaceClass.CFD_DENSITY:
        system = "CFD Auxiliary"
    elif surface_class is SurfaceClass.PYLON:
        system = "Pylon"
    else:
        for prefix, sys_name in _SYSTEM_BY_PREFIX:
            if component_key.startswith(prefix) or component_key == prefix.rstrip("_"):
                system = sys_name
                break

    component = component_key.replace("_", " ").strip()
    return FpdFile(
        path=path,
        stem=stem,
        surface_class=surface_class,
        component=component,
        system=system,
        role=role,
    )


def discover(config: Config) -> list[FpdFile]:
    """Discover and classify all FPD files under ``config.fpd_dir``.

    Args:
        config: Run configuration.

    Returns:
        Sorted list of classified :class:`FpdFile` records.

    Raises:
        DiscoveryError: If the directory is missing or contains no FPD files.
    """
    fpd_dir = config.fpd_dir
    if not fpd_dir.is_dir():
        raise DiscoveryError(f"FPD directory does not exist: {fpd_dir}")

    paths = sorted(fpd_dir.glob("*.fpd"))
    if not paths:
        raise DiscoveryError(f"No .fpd files found in {fpd_dir}")

    # Duplicate detection by stem (case-insensitive).
    seen: dict[str, Path] = {}
    duplicates: list[str] = []
    for p in paths:
        key = p.stem.lower()
        if key in seen:
            duplicates.append(p.name)
        else:
            seen[key] = p
    if duplicates:
        raise DiscoveryError(f"Duplicate FPD file stems detected: {duplicates}")

    files = [classify(p) for p in paths]

    n_total = len(files)
    by_class: dict[SurfaceClass, int] = {}
    for f in files:
        by_class[f.surface_class] = by_class.get(f.surface_class, 0) + 1

    logger.info(
        "Discovered %d FPD files (engine_body=%d, pylon=%d, cfd_density=%d, unknown=%d)",
        n_total,
        by_class.get(SurfaceClass.ENGINE_BODY, 0),
        by_class.get(SurfaceClass.PYLON, 0),
        by_class.get(SurfaceClass.CFD_DENSITY, 0),
        by_class.get(SurfaceClass.UNKNOWN, 0),
    )
    if n_total != config.expected_fpd_count:
        logger.warning("Expected %d FPD files but found %d", config.expected_fpd_count, n_total)
    return files
