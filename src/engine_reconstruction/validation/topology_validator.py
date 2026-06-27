"""Stage 5b — validate the recovered topology graph.

Checks that the engine-body surfaces form a single connected adjacency component
(a prerequisite for one merged shell) and that all expected components are
present. Findings are advisory by default; connectivity is the key signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..infrastructure.logging import get_logger
from ..topology import expected_topology
from ..topology.topology_analyser import TopologyResult

logger = get_logger(__name__)


@dataclass
class TopologyValidationReport:
    """Outcome of validating the adjacency graph."""

    connected: bool
    n_graph_components: int
    largest_component_size: int
    isolated_surfaces: list[str] = field(default_factory=list)
    missing_components: list[str] = field(default_factory=list)
    passed: bool = False
    notes: list[str] = field(default_factory=list)


def validate_topology(result: TopologyResult) -> TopologyValidationReport:
    """Validate the engine-body adjacency graph for connectivity/completeness."""
    components = result.graph.connected_components()
    components.sort(key=len, reverse=True)
    largest = components[0] if components else set()
    isolated = sorted(name for comp in components if len(comp) == 1 for name in comp)
    expected = set(expected_topology.ENGINE_BODY_COMPONENTS)
    missing = sorted(expected - set(result.components))

    connected = len(components) <= 1
    rep = TopologyValidationReport(
        connected=connected,
        n_graph_components=len(components),
        largest_component_size=len(largest),
        isolated_surfaces=isolated,
        missing_components=missing,
    )
    rep.passed = connected and not missing
    if not connected:
        rep.notes.append(
            f"engine-body adjacency graph has {len(components)} disconnected groups; "
            "a single merged shell requires one connected group"
        )
    if missing:
        rep.notes.append(f"missing expected components: {missing}")
    if isolated:
        rep.notes.append(f"surfaces with no detected neighbour: {isolated}")

    log = logger.info if rep.passed else logger.warning
    log(
        "Topology validation: connected=%s components=%d largest=%d missing=%d",
        connected,
        rep.n_graph_components,
        rep.largest_component_size,
        len(missing),
    )
    return rep
