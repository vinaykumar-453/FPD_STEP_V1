"""Stage 5 — recover topology: classification, components, adjacency graph.

Hybrid strategy:
  * **Auto-derive** the physical/CFD classification and the inboard/outboard
    component grouping from file names + geometry.
  * **Optionally override / validate** against an external CSV
    (``rb3135_topology.csv``) when ``config.use_topology_csv_override`` is set
    and the file exists. Conflicts are logged, never silently applied.

Adjacency (coincident boundaries) is computed geometrically over the
engine-body surfaces, which is what the merged shell is built from.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..infrastructure.config import Config
from ..infrastructure.data_types import FpdFile, SeamMatch, StructuredGrid, SurfaceClass
from ..infrastructure.logging import get_logger
from . import expected_topology, neighbour_detector
from .topology_graph import TopologyGraph

logger = get_logger(__name__)

_CONFIG_SUFFIX = re.compile(r"[_-](?:free[_-]flying|installed|uninstalled)$", re.IGNORECASE)
_ROLE_TOKENS = ("inboard", "outboard")


def component_key(stem: str) -> str:
    """Derive the underscore component key (e.g. ``BP_inner``) from a file stem."""
    base = _CONFIG_SUFFIX.sub("", stem)
    for tok in _ROLE_TOKENS:
        if base.lower().endswith("_" + tok):
            return base[: -(len(tok) + 1)]
    return base


@dataclass
class TopologyResult:
    """Outcome of topology recovery."""

    surface_class: dict[str, SurfaceClass] = field(default_factory=dict)
    components: dict[str, list[str]] = field(default_factory=dict)  # engine body
    engine_body_surfaces: list[str] = field(default_factory=list)
    graph: TopologyGraph = field(default_factory=TopologyGraph)
    seam_matches: list[SeamMatch] = field(default_factory=list)
    override_conflicts: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def _load_csv_classification(csv_path: Path) -> dict[str, SurfaceClass]:
    """Read the optional topology CSV -> stem -> SurfaceClass (physical/CFD)."""
    out: dict[str, SurfaceClass] = {}
    with csv_path.open("r", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            stem = (row.get("File Name") or "").strip()
            if not stem:
                continue
            physical = (row.get("Physical Surface?") or "").strip().lower() == "yes"
            if not physical:
                out[stem] = SurfaceClass.CFD_DENSITY
            elif stem.lower().startswith("pylon"):
                out[stem] = SurfaceClass.PYLON
            else:
                out[stem] = SurfaceClass.ENGINE_BODY
    return out


def analyse(
    files: list[FpdFile],
    grids: dict[str, StructuredGrid],
    config: Config,
) -> TopologyResult:
    """Recover topology for the discovered surfaces.

    Args:
        files: Classified FPD files from discovery.
        grids: Oriented grids keyed by surface stem (subset that parsed OK).
        config: Run configuration.

    Returns:
        A populated :class:`TopologyResult`.
    """
    result = TopologyResult()

    # --- classification (name-based, optionally validated by CSV) ---
    csv_class: dict[str, SurfaceClass] = {}
    if config.use_topology_csv_override and config.topology_csv and config.topology_csv.exists():
        try:
            csv_class = _load_csv_classification(config.topology_csv)
            logger.info("Loaded topology CSV override: %d rows", len(csv_class))
        except Exception as exc:
            logger.warning("Failed to read topology CSV %s: %s", config.topology_csv, exc)

    for f in files:
        cls = f.surface_class
        override = csv_class.get(f.stem)
        if override is not None and override != cls:
            result.override_conflicts.append(
                f"{f.stem}: name={cls.value} -> csv={override.value} (using csv)"
            )
            cls = override
        result.surface_class[f.stem] = cls

    # --- engine-body component grouping (prefix match against the skeleton) ---
    for f in files:
        if result.surface_class[f.stem] is not SurfaceClass.ENGINE_BODY:
            continue
        comp = expected_topology.match_engine_component(f.stem)
        if comp is None:
            # Fall back to the derived key so the surface is still tracked, but it
            # won't be picked up by the skeleton-driven assembly.
            logger.warning("Engine-body surface %s matched no skeleton component", f.stem)
            comp = component_key(f.stem)
        result.components.setdefault(comp, []).append(f.stem)
        result.engine_body_surfaces.append(f.stem)
    result.engine_body_surfaces.sort()

    # --- adjacency graph over engine-body grids that parsed OK ---
    eb_grids = {name: grids[name] for name in result.engine_body_surfaces if name in grids}
    for name in eb_grids:
        result.graph.add_node(name)
    result.seam_matches = neighbour_detector.detect_all(eb_grids, config)
    for m in result.seam_matches:
        result.graph.add_match(m)

    # --- summary + sanity vs expected topology ---
    by_class: dict[str, int] = {}
    for cls in result.surface_class.values():
        by_class[cls.value] = by_class.get(cls.value, 0) + 1
    components_found = sorted(result.components)
    expected = set(expected_topology.ENGINE_BODY_COMPONENTS)
    missing = sorted(expected - set(components_found))
    extra = sorted(set(components_found) - expected)
    if missing:
        logger.warning("Expected engine-body components missing: %s", missing)
    if extra:
        logger.warning("Unexpected engine-body component keys: %s", extra)

    result.summary = {
        "n_surfaces": len(files),
        "n_engine_body": by_class.get(SurfaceClass.ENGINE_BODY.value, 0),
        "n_pylon": by_class.get(SurfaceClass.PYLON.value, 0),
        "n_cfd_density": by_class.get(SurfaceClass.CFD_DENSITY.value, 0),
        "n_components": len(result.components),
        "n_seam_matches": len(result.seam_matches),
        "graph_edges": result.graph.edge_count(),
        "graph_components": len(result.graph.connected_components()),
        "missing_components": len(missing),
        "override_conflicts": len(result.override_conflicts),
    }
    logger.info("Topology summary: %s", result.summary)
    return result
