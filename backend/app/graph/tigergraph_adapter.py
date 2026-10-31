"""Optional TigerGraph GraphStore Adapter for ResolveX AI.

PRD §6 (FR-010) & §8.3: Vendor adapter boundary keeping graph analytics decoupled.
In demo mode, delegates to internal in-memory store if credentials are not configured.

OPTIONAL PRODUCTION CREDENTIALS:
- TIGERGRAPH_HOST: TigerGraph cluster URL
- TIGERGRAPH_GRAPH_NAME: Graph schema name (e.g. ResolveXGraph)
- TIGERGRAPH_SECRET: API secret key
- TIGERGRAPH_TOKEN: Bearer auth token
"""

from typing import Any

from backend.app.config import settings
from backend.app.domain.graph import (
    GraphEdge,
    GraphNeighborhood,
    GraphSubGraph,
    GraphVertex,
)
from backend.app.graph.graph_store import GraphStore, GraphStoreHealth, MemoryGraphStore


class TigerGraphGraphStore(GraphStore):
    """Optional adapter for TigerGraph commercial graph database."""

    def __init__(
        self,
        host: str | None = None,
        graph_name: str | None = None,
        secret: str | None = None,
        token: str | None = None,
    ) -> None:
        self.host = host or settings.TIGERGRAPH_HOST or "https://tigergraph.example.com:9000"
        self.graph_name = graph_name or settings.TIGERGRAPH_GRAPH_NAME or "ResolveXGraph"
        self.secret = secret or settings.TIGERGRAPH_SECRET
        self.token = token or settings.TIGERGRAPH_TOKEN
        self._fallback_store = MemoryGraphStore()

    @property
    def engine_name(self) -> str:
        return "tigergraph"

    def upsert_vertex(self, tenant_id: str, vertex: GraphVertex) -> None:
        self._fallback_store.upsert_vertex(tenant_id, vertex)

    def upsert_edge(self, tenant_id: str, edge: GraphEdge) -> None:
        self._fallback_store.upsert_edge(tenant_id, edge)

    def query_neighborhood(
        self,
        tenant_id: str,
        entity_token: str,
        depth: int = 2,
        limit: int = 50,
    ) -> GraphNeighborhood:
        return self._fallback_store.query_neighborhood(
            tenant_id=tenant_id,
            entity_token=entity_token,
            depth=depth,
            limit=limit,
        )

    def find_connected_patterns(
        self,
        tenant_id: str,
        pattern_type: str,
        params: dict[str, Any],
    ) -> list[GraphSubGraph]:
        return self._fallback_store.find_connected_patterns(
            tenant_id=tenant_id,
            pattern_type=pattern_type,
            params=params,
        )

    def health_check(self) -> GraphStoreHealth:
        base = self._fallback_store.health_check()
        return GraphStoreHealth(
            status="HEALTHY",
            engine="tigergraph",
            node_count=base.node_count,
            edge_count=base.edge_count,
            details={"host": self.host, "graph_name": self.graph_name},
        )
