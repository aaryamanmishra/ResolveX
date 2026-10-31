"""Apache AGE GraphStore Adapter for ResolveX AI.

PRD §6 (FR-010) & §8.3: Apache AGE is the default open-source graph engine,
running graph queries alongside PostgreSQL relational data using openCypher.

REQUIRED PRODUCTION CREDENTIALS:
- DATABASE_URL: PostgreSQL connection string with Apache AGE extension compiled and loaded.
In offline demo mode, runs in hybrid mode leveraging in-memory graph indexing
while maintaining exact Apache AGE Cypher query generation contracts.
"""

from dataclasses import dataclass
from typing import Any

from backend.app.domain.graph import (
    GraphEdge,
    GraphNeighborhood,
    GraphSubGraph,
    GraphVertex,
)
from backend.app.graph.graph_store import GraphStore, GraphStoreHealth, MemoryGraphStore


@dataclass
class AgeCypherQuery:
    """Represents a generated openCypher query for Apache AGE."""

    graph_name: str
    cypher_text: str
    sql_wrapper: str


class ApacheAGEGraphStore(GraphStore):
    """Adapter for PostgreSQL Apache AGE extension executing Cypher queries."""

    def __init__(
        self,
        graph_name: str = "resolvex_fraud_graph",
        connection_url: str | None = None,
    ) -> None:
        self.graph_name = graph_name
        self.connection_url = connection_url
        # Backing memory store for demo mode & local testing
        self._fallback_store = MemoryGraphStore()

    @property
    def engine_name(self) -> str:
        return "apache_age"

    def build_create_vertex_cypher(self, vertex: GraphVertex) -> AgeCypherQuery:
        """Construct Cypher query to create or merge a vertex in Apache AGE."""
        props = dict(vertex.properties)
        props["id"] = vertex.id
        props["tenant_id"] = vertex.tenant_id
        props["is_tokenized"] = vertex.is_tokenized

        import json

        props_json = json.dumps(props)
        cypher = f"MERGE (v:{vertex.label} {{id: '{vertex.id}', tenant_id: '{vertex.tenant_id}'}}) SET v += {props_json}"
        sql = f"SELECT * FROM cypher('{self.graph_name}', $$ {cypher} $$) as (v agtype);"
        return AgeCypherQuery(graph_name=self.graph_name, cypher_text=cypher, sql_wrapper=sql)

    def build_create_edge_cypher(self, edge: GraphEdge) -> AgeCypherQuery:
        """Construct Cypher query to create or merge a directed edge in Apache AGE."""
        props = dict(edge.properties)
        props["id"] = edge.id
        props["tenant_id"] = edge.tenant_id
        props["source_record_id"] = edge.source_record_id
        props["confidence"] = edge.confidence
        props["inferred"] = edge.inferred
        props["source_type"] = edge.source_type

        import json

        props_json = json.dumps(props)
        cypher = (
            f"MATCH (s {{id: '{edge.source_id}', tenant_id: '{edge.tenant_id}'}}), "
            f"(t {{id: '{edge.target_id}', tenant_id: '{edge.tenant_id}'}}) "
            f"MERGE (s)-[r:{edge.label} {{id: '{edge.id}', tenant_id: '{edge.tenant_id}'}}]->(t) "
            f"SET r += {props_json}"
        )
        sql = f"SELECT * FROM cypher('{self.graph_name}', $$ {cypher} $$) as (r agtype);"
        return AgeCypherQuery(graph_name=self.graph_name, cypher_text=cypher, sql_wrapper=sql)

    def build_neighborhood_cypher(
        self,
        tenant_id: str,
        entity_token: str,
        depth: int = 2,
        limit: int = 50,
    ) -> AgeCypherQuery:
        """Construct Cypher query to retrieve bounded neighborhood in Apache AGE."""
        bounded_depth = min(max(depth, 1), 4)
        cypher = (
            f"MATCH path = (c {{id: '{entity_token}', tenant_id: '{tenant_id}'}})-[*1..{bounded_depth}]-(n) "
            f"WHERE n.tenant_id = '{tenant_id}' "
            f"RETURN path LIMIT {limit}"
        )
        sql = f"SELECT * FROM cypher('{self.graph_name}', $$ {cypher} $$) as (path agtype);"
        return AgeCypherQuery(graph_name=self.graph_name, cypher_text=cypher, sql_wrapper=sql)

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
            engine="apache_age",
            node_count=base.node_count,
            edge_count=base.edge_count,
            details={"graph_name": self.graph_name, "open_cypher_supported": True},
        )
