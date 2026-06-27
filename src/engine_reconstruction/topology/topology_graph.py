"""Stage 4/5 — adjacency graph over surfaces.

A light, dependency-free undirected graph: nodes are surface names, edges record
that two surfaces share at least one coincident boundary (with the best/lowest
RMS observed). Provides connected-component discovery for sanity checks.
"""

from __future__ import annotations

from collections import defaultdict

from ..infrastructure.data_types import SeamMatch


class TopologyGraph:
    """Undirected adjacency graph of surfaces linked by coincident boundaries."""

    def __init__(self) -> None:
        self._adj: dict[str, dict[str, float]] = defaultdict(dict)
        self._nodes: set[str] = set()

    def add_node(self, name: str) -> None:
        self._nodes.add(name)
        _ = self._adj[name]

    def add_match(self, match: SeamMatch) -> None:
        a, b = match.surface_a, match.surface_b
        self._nodes.update((a, b))
        prev = self._adj[a].get(b)
        if prev is None or match.rms < prev:
            self._adj[a][b] = match.rms
            self._adj[b][a] = match.rms

    @property
    def nodes(self) -> set[str]:
        return set(self._nodes)

    def neighbours(self, name: str) -> dict[str, float]:
        return dict(self._adj.get(name, {}))

    def edge_count(self) -> int:
        return sum(len(v) for v in self._adj.values()) // 2

    def connected_components(self) -> list[set[str]]:
        """Return connected components as a list of node sets."""
        seen: set[str] = set()
        components: list[set[str]] = []
        for start in sorted(self._nodes):
            if start in seen:
                continue
            stack = [start]
            comp: set[str] = set()
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                comp.add(node)
                stack.extend(self._adj[node].keys())
            components.append(comp)
        return components
