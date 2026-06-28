"""Stage 1 — discover and classify FPD files.

Globs the FPD directory, validates the inventory (count, duplicates, naming),
and classifies each file by name into an engine-body / pylon / CFD-density
:class:`SurfaceClass` together with a component key, system, and role token.

Classification here is *name-based* and fast; the topology stage may later
refine or override it (geometry-based auto-derivation + optional CSV).
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from ..infrastructure.config import Config
from ..infrastructure.data_types import FpdFile, SurfaceClass
from ..infrastructure.exceptions import DiscoveryError
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)

# A dataset/configuration suffix tags the export variant of a surface, e.g.
# "_free-flying", "_installed", "_uninstalled". It is stripped before
# classification and component matching.
_CONFIG_SUFFIX = re.compile(r"[_-](?:free[_-]flying|installed|uninstalled)$", re.IGNORECASE)
_CONFIG_TAG = re.compile(r"[_-](installed|uninstalled)$", re.IGNORECASE)
_ROLE_TOKENS = ("inboard", "outboard")
# Characters that switch a pattern from "substring" to "glob" matching.
_GLOB_META = re.compile(r"[*?\[]")

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
    return _CONFIG_SUFFIX.sub("", stem)


def config_tag(stem: str) -> str | None:
    """Return the configuration tag of a file stem, or ``None``.

    ``"BP_inner_inboard_installed"`` -> ``"installed"``;
    ``"Spinner_inboard_free-flying"`` -> ``None`` (no installed/uninstalled tag).
    """
    m = _CONFIG_TAG.search(stem)
    return m.group(1).lower() if m else None


def matches_exclude(stem: str, patterns: tuple[str, ...]) -> bool:
    """Return ``True`` if ``stem`` should be ignored per the exclusion patterns.

    Matching is case-insensitive. Each pattern is interpreted as:

    * a **glob** (``fnmatch`` against the full stem) if it contains a glob
      metacharacter (``*`` ``?`` ``[``), e.g. ``"Pylon_*_cutoff_*"``;
    * otherwise a plain **substring** match, e.g. ``"heatshield"`` drops every
      file whose name contains it.

    Args:
        stem: FPD file stem (the configuration suffix is still attached).
        patterns: Exclusion patterns from :attr:`Config.exclude_patterns`.

    Returns:
        Whether ``stem`` matches any pattern.
    """
    s = stem.lower()
    for pat in patterns:
        p = pat.strip()
        if not p:
            continue
        p_low = p.lower()
        if _GLOB_META.search(p):
            if fnmatch.fnmatch(s, p_low):
                return True
        elif p_low in s:
            return True
    return False


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

    all_paths = sorted(fpd_dir.glob("*.fpd"))
    if not all_paths:
        raise DiscoveryError(f"No .fpd files found in {fpd_dir}")

    # Configuration filter: when files are tagged "_installed"/"_uninstalled",
    # keep only the selected configuration. Untagged files are always kept.
    wanted = config.configuration.strip().lower()
    paths = [p for p in all_paths if (config_tag(p.stem) or wanted) == wanted]
    n_dropped = len(all_paths) - len(paths)
    if n_dropped:
        logger.info(
            "Configuration '%s': kept %d of %d files (%d other-configuration files skipped)",
            wanted,
            len(paths),
            len(all_paths),
            n_dropped,
        )
    if not paths:
        raise DiscoveryError(f"No .fpd files match configuration '{wanted}' in {fpd_dir}")

    # Exclusion filter: drop surfaces whose stem matches a configured name
    # pattern. Excluded files are ignored everywhere downstream (parse, fit,
    # sew, export, metadata) — this is the single gate for "ignore this surface".
    if config.exclude_patterns:
        excluded = [p for p in paths if matches_exclude(p.stem, config.exclude_patterns)]
        if excluded:
            paths = [p for p in paths if p not in excluded]
            logger.info(
                "Exclusion patterns %s: ignoring %d file(s): %s",
                list(config.exclude_patterns),
                len(excluded),
                sorted(p.stem for p in excluded),
            )
        if not paths:
            raise DiscoveryError(
                f"All files excluded by patterns {list(config.exclude_patterns)} in {fpd_dir}"
            )

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
    if config.expected_fpd_count is not None and n_total != config.expected_fpd_count:
        logger.warning("Expected %d FPD files but found %d", config.expected_fpd_count, n_total)
    return files
