"""Graph Store Protocol and In-Memory Graph Implementation for ResolveX AI.

PRD §6 (FR-010), §7.3 & §8.3: GraphStore interface ensures queries are decoupled
from the underlying graph engine.
- Apache AGE (open source PostgreSQL extension) is the default production target.
- TigerGraph adapter is optional for specialized benchmarks.
- In-memory GraphStore provides zero-dependency testing and local demo capability.

EXTERNAL CREDENTIALS REQUIRED IN PRODUCTION:
- DATABASE_URL: PostgreSQL connection string with Apache AGE loaded
- TIGERGRAPH_HOST / TIGERGRAPH_SECRET / TIGERGRAPH_TOKEN: (Optional, only if TigerGraph adapter is enabled)
In demo mode, MemoryGraphStore runs in-process with zero external configuration.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from backend.app.domain.graph import (
    GraphEdge,
    GraphNeighborhood,
    GraphSubGraph,
    GraphVertex,
)


@dataclass(frozen=True)
class GraphStoreHealth:
    status: str  # "HEALTHY", "DEGRADED", "UNAVAILABLE"
    engine: str  # "apache_age", "memory", "tigergraph"
    node_count: int
    edge_count: int
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class GraphStore(Protocol):
    """Protocol defining the graph database abstraction for fraud investigations."""

    @property
    def engine_name(self) -> str: ...

    def upsert_vertex(self, tenant_id: str, vertex: GraphVertex) -> None:
        """Insert or update a graph vertex. Must enforce tenant boundary."""
        ...

    def upsert_edge(self, tenant_id: str, edge: GraphEdge) -> None:
        """Insert or update a directed graph edge. Must enforce tenant boundary."""
        ...

    def query_neighborhood(
        self,
        tenant_id: str,
        entity_token: str,
        depth: int = 2,
        limit: int = 50,
    ) -> GraphNeighborhood:
        """Bounded graph traversal around an entity token within a single tenant."""
        ...

    def find_connected_patterns(
        self,
        tenant_id: str,
        pattern_type: str,
        params: dict[str, Any],
    ) -> list[GraphSubGraph]:
        """Detect deterministic suspicious patterns (e.g. shared device clustering)."""
        ...

    def health_check(self) -> GraphStoreHealth: ...


class MemoryGraphStore:
    """In-memory, tenant-isolated graph store for testing and zero-dependency local runs."""

    def __init__(self) -> None:
        # Keyed by (tenant_id, vertex_id) -> GraphVertex
        self._vertices: dict[tuple[str, str], GraphVertex] = {}
        # Keyed by (tenant_id, edge_id) -> GraphEdge
        self._edges: dict[tuple[str, str], GraphEdge] = {}
        # Adjacency index: (tenant_id, source_id) -> set of edge_ids
        self._out_edges: dict[tuple[str, str], set[str]] = {}
        # Reverse adjacency index: (tenant_id, target_id) -> set of edge_ids
        self._in_edges: dict[tuple[str, str], set[str]] = {}

    def clear(self) -> None:
        """Reset in-memory graph store for testing."""
        self._vertices.clear()
        self._edges.clear()
        self._out_edges.clear()
        self._in_edges.clear()

    @property
    def engine_name(self) -> str:
        return "memory"

    def upsert_vertex(self, tenant_id: str, vertex: GraphVertex) -> None:
        if vertex.tenant_id != tenant_id:
            raise ValueError(
                f"Vertex tenant_id '{vertex.tenant_id}' must match store tenant_id '{tenant_id}'"
            )
        self._vertices[(tenant_id, vertex.id)] = vertex

    def upsert_edge(self, tenant_id: str, edge: GraphEdge) -> None:
        if edge.tenant_id != tenant_id:
            raise ValueError(
                f"Edge tenant_id '{edge.tenant_id}' must match store tenant_id '{tenant_id}'"
            )

        self._edges[(tenant_id, edge.id)] = edge

        out_key = (tenant_id, edge.source_id)
        if out_key not in self._out_edges:
            self._out_edges[out_key] = set()
        self._out_edges[out_key].add(edge.id)

        in_key = (tenant_id, edge.target_id)
        if in_key not in self._in_edges:
            self._in_edges[in_key] = set()
        self._in_edges[in_key].add(edge.id)

    def query_neighborhood(
        self,
        tenant_id: str,
        entity_token: str,
        depth: int = 2,
        limit: int = 50,
    ) -> GraphNeighborhood:
        bounded_depth = min(max(depth, 1), 4)

        start_key = (tenant_id, entity_token)
        if start_key not in self._vertices:
            return GraphNeighborhood(
                center_vertex_id=entity_token,
                depth=bounded_depth,
                vertices=[],
                edges=[],
                total_nodes=0,
                total_edges=0,
            )

        visited_nodes: dict[str, GraphVertex] = {entity_token: self._vertices[start_key]}
        collected_edges: dict[str, GraphEdge] = {}

        # BFS bounded queue: (current_vertex_id, current_distance)
        queue: deque[tuple[str, int]] = deque([(entity_token, 0)])

        while queue and len(visited_nodes) < limit:
            current_id, current_dist = queue.popleft()
            if current_dist >= bounded_depth:
                continue

            # Check outgoing edges
            out_edge_ids = self._out_edges.get((tenant_id, current_id), set())
            for eid in out_edge_ids:
                edge = self._edges[(tenant_id, eid)]
                collected_edges[edge.id] = edge
                neighbor_id = edge.target_id
                neighbor_key = (tenant_id, neighbor_id)
                if neighbor_key in self._vertices and neighbor_id not in visited_nodes:
                    visited_nodes[neighbor_id] = self._vertices[neighbor_key]
                    queue.append((neighbor_id, current_dist + 1))
                if len(visited_nodes) >= limit:
                    break

            # Check incoming edges (bidirectional relationship expansion)
            in_edge_ids = self._in_edges.get((tenant_id, current_id), set())
            for eid in in_edge_ids:
                edge = self._edges[(tenant_id, eid)]
                collected_edges[edge.id] = edge
                neighbor_id = edge.source_id
                neighbor_key = (tenant_id, neighbor_id)
                if neighbor_key in self._vertices and neighbor_id not in visited_nodes:
                    visited_nodes[neighbor_id] = self._vertices[neighbor_key]
                    queue.append((neighbor_id, current_dist + 1))
                if len(visited_nodes) >= limit:
                    break

        return GraphNeighborhood(
            center_vertex_id=entity_token,
            depth=bounded_depth,
            vertices=list(visited_nodes.values()),
            edges=list(collected_edges.values()),
            total_nodes=len(visited_nodes),
            total_edges=len(collected_edges),
        )

    def find_connected_patterns(
        self,
        tenant_id: str,
        pattern_type: str,
        params: dict[str, Any],
    ) -> list[GraphSubGraph]:
        results: list[GraphSubGraph] = []

        if pattern_type == "shared_device":
            # Detect devices linked to > threshold customers
            threshold = params.get("threshold", 3)
            # Find device vertices
            device_vertices = [
                v
                for (t, _), v in self._vertices.items()
                if t == tenant_id and v.label == "DeviceToken"
            ]

            for device in device_vertices:
                # Find all USED_DEVICE edges targeting this device
                in_edges = [
                    self._edges[(tenant_id, eid)]
                    for eid in self._in_edges.get((tenant_id, device.id), set())
                    if self._edges[(tenant_id, eid)].label == "USED_DEVICE"
                ]

                # Find source nodes
                sources = [
                    self._vertices[(tenant_id, e.source_id)]
                    for e in in_edges
                    if (tenant_id, e.source_id) in self._vertices
                ]

                if len(sources) >= threshold:
                    results.append(
                        GraphSubGraph(
                            pattern_name="shared_device_cluster",
                            nodes=[device, *sources],
                            edges=in_edges,
                            risk_score=min(0.2 * len(sources), 1.0),
                            reason_codes=["SHARED_DEVICE_THRESHOLD_EXCEEDED"],
                        )
                    )

        return results

    def health_check(self) -> GraphStoreHealth:
        return GraphStoreHealth(
            status="HEALTHY",
            engine="memory",
            node_count=len(self._vertices),
            edge_count=len(self._edges),
            details={"demo_mode": True},
        )
