"""GraphStore factory for ResolveX AI."""

from backend.app.config import settings
from backend.app.graph.age_adapter import ApacheAGEGraphStore
from backend.app.graph.graph_store import GraphStore, MemoryGraphStore
from backend.app.graph.tigergraph_adapter import TigerGraphGraphStore


def get_graph_store() -> GraphStore:
    """Instantiate the configured GraphStore adapter."""
    engine = settings.GRAPH_ENGINE.lower()
    if engine == "apache_age":
        return ApacheAGEGraphStore()
    if engine == "tigergraph":
        return TigerGraphGraphStore()
    return MemoryGraphStore()
