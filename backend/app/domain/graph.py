"""Graph domain models and graph representation for ResolveX AI.

PRD §7.3: Defines vertices and edges for relationship investigations.
Identifiers are tokenized with tenant-scoped HMAC before graph insertion.
Every edge carries source_record_id, observed_at, confidence, and inferred flags.
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import Field

from backend.app.domain.payment import BaseDomainModel


class VertexLabel(StrEnum):
    """Canonical graph vertex labels."""

    CUSTOMER_TOKEN = "CustomerToken"
    PAYMENT = "Payment"
    MERCHANT = "Merchant"
    DEVICE_TOKEN = "DeviceToken"
    PAYMENT_INSTRUMENT_TOKEN = "PaymentInstrumentToken"
    UPI_REFERENCE_TOKEN = "UPIReferenceToken"
    IP_ADDRESS_TOKEN = "IPAddressToken"
    REFUND = "Refund"
    CASE = "Case"
    PROVIDER_EVENT = "ProviderEvent"


class EdgeLabel(StrEnum):
    """Canonical graph edge labels."""

    INITIATED_BY = "INITIATED_BY"
    PAID_TO = "PAID_TO"
    USED_DEVICE = "USED_DEVICE"
    USED_INSTRUMENT = "USED_INSTRUMENT"
    HAS_REFERENCE = "HAS_REFERENCE"
    LINKED_REFUND = "LINKED_REFUND"
    FLAGGED_IN_CASE = "FLAGGED_IN_CASE"
    SAME_TOKEN_AS = "SAME_TOKEN_AS"
    PREVIOUSLY_REVIEWED_WITH = "PREVIOUSLY_REVIEWED_WITH"


class GraphVertex(BaseDomainModel):
    """Vertex in the fraud relationship graph."""

    id: str = Field(..., description="Unique vertex ID e.g. cust_tok_abc123")
    tenant_id: str = Field(..., description="Tenant boundary")
    label: VertexLabel = Field(..., description="Type of vertex")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Metadata properties (never raw PII or secrets)"
    )
    is_tokenized: bool = Field(
        default=True, description="Indicates whether sensitive values have been HMAC tokenized"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GraphEdge(BaseDomainModel):
    """Directed edge representing an observed or inferred relationship."""

    id: str = Field(..., description="Unique edge identifier")
    tenant_id: str = Field(..., description="Tenant boundary")
    source_id: str = Field(..., description="Source vertex ID")
    target_id: str = Field(..., description="Target vertex ID")
    label: EdgeLabel = Field(..., description="Relationship type")
    source_record_id: str = Field(
        ..., description="Underlying database record ID e.g. payment_id or event_id"
    )
    observed_at: datetime = Field(..., description="Timestamp relationship was observed")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence of relationship")
    source_type: str = Field(
        default="PAYMENT_EVENT", description="Origin of link e.g. PAYMENT_EVENT, DEVICE_FINGERPRINT"
    )
    inferred: bool = Field(
        default=False,
        description="True if relationship is inferred by heuristics rather than directly observed",
    )
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphNeighborhood(BaseDomainModel):
    """Bounded subgraph returned from an investigation traversal."""

    center_vertex_id: str
    depth: int = Field(..., ge=1, le=4, description="Search depth (bounded)")
    vertices: list[GraphVertex] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_nodes: int = Field(default=0, ge=0)
    total_edges: int = Field(default=0, ge=0)


class GraphSubGraph(BaseDomainModel):
    """Pattern match subgraph (e.g. shared device network or velocity burst)."""

    pattern_name: str
    nodes: list[GraphVertex]
    edges: list[GraphEdge]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
