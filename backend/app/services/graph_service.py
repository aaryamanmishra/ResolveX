"""Graph Materialization and Investigation Service for ResolveX AI.

PRD §7.3 & §6 (FR-010, FR-011): Materializes tokenized vertices and edges
from transactions and payment events. Ensures sensitive identifiers are
tokenized via tenant-keyed HMAC before graph storage.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from backend.app.domain.graph import (
    EdgeLabel,
    GraphEdge,
    GraphNeighborhood,
    GraphVertex,
    VertexLabel,
)
from backend.app.domain.payment import Payment
from backend.app.graph.factory import get_graph_store
from backend.app.graph.graph_store import GraphStore
from backend.app.security.context import TenantContext
from backend.app.security.tokenization import Tokenizer
from backend.app.services.audit_service import audit_service


class GraphService:
    """Manages graph materialization, bounded traversals, and fraud evidence linkage."""

    def __init__(self, store: GraphStore | None = None) -> None:
        self.store = store or get_graph_store()
        self.tokenizer = Tokenizer()

    def materialize_transaction(
        self,
        ctx: TenantContext,
        payment: Payment,
        raw_customer_id: str,
        raw_device_id: str | None = None,
        raw_card_fingerprint: str | None = None,
        raw_upi_reference: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Tokenize entities with tenant-scoped HMAC and materialize vertices/edges into graph."""
        now = datetime.now(timezone.utc)
        tenant_id = ctx.tenant_id

        # 1. Tokenize Identifiers (never store raw values in graph)
        cust_token = self.tokenizer.tokenize(tenant_id, raw_customer_id, prefix="cust")
        dev_token = (
            self.tokenizer.tokenize(tenant_id, raw_device_id, prefix="dev")
            if raw_device_id
            else None
        )
        card_token = (
            self.tokenizer.tokenize(tenant_id, raw_card_fingerprint, prefix="inst")
            if raw_card_fingerprint
            else None
        )
        upi_token = (
            self.tokenizer.tokenize(tenant_id, raw_upi_reference, prefix="upi")
            if raw_upi_reference
            else None
        )

        # 2. Materialize Vertices
        v_payment = GraphVertex(
            id=payment.id,
            tenant_id=tenant_id,
            label=VertexLabel.PAYMENT,
            properties={
                "amount_minor": payment.amount_minor,
                "currency": payment.currency,
                "status": payment.payment_status.value,
                "order_ref": payment.order_ref,
            },
            is_tokenized=False,
            created_at=now,
        )
        self.store.upsert_vertex(tenant_id, v_payment)

        v_cust = GraphVertex(
            id=cust_token,
            tenant_id=tenant_id,
            label=VertexLabel.CUSTOMER_TOKEN,
            properties={"token_type": "hmac_sha256"},
            is_tokenized=True,
            created_at=now,
        )
        self.store.upsert_vertex(tenant_id, v_cust)

        v_merchant = GraphVertex(
            id=payment.merchant_id,
            tenant_id=tenant_id,
            label=VertexLabel.MERCHANT,
            properties={},
            is_tokenized=False,
            created_at=now,
        )
        self.store.upsert_vertex(tenant_id, v_merchant)

        created_edges: list[GraphEdge] = []

        # 3. Materialize Edges
        # Customer -[INITIATED_BY]-> Payment
        edge_initiated = GraphEdge(
            id=f"edge_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            source_id=cust_token,
            target_id=payment.id,
            label=EdgeLabel.INITIATED_BY,
            source_record_id=payment.id,
            observed_at=now,
            confidence=1.0,
            source_type="PAYMENT_RECORD",
            inferred=False,
        )
        self.store.upsert_edge(tenant_id, edge_initiated)
        created_edges.append(edge_initiated)

        # Payment -[PAID_TO]-> Merchant
        edge_paid_to = GraphEdge(
            id=f"edge_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            source_id=payment.id,
            target_id=payment.merchant_id,
            label=EdgeLabel.PAID_TO,
            source_record_id=payment.id,
            observed_at=now,
            confidence=1.0,
            source_type="PAYMENT_RECORD",
            inferred=False,
        )
        self.store.upsert_edge(tenant_id, edge_paid_to)
        created_edges.append(edge_paid_to)

        # Customer -[USED_DEVICE]-> DeviceToken
        if dev_token:
            v_device = GraphVertex(
                id=dev_token,
                tenant_id=tenant_id,
                label=VertexLabel.DEVICE_TOKEN,
                properties={},
                is_tokenized=True,
                created_at=now,
            )
            self.store.upsert_vertex(tenant_id, v_device)

            edge_dev = GraphEdge(
                id=f"edge_{uuid.uuid4().hex[:12]}",
                tenant_id=tenant_id,
                source_id=cust_token,
                target_id=dev_token,
                label=EdgeLabel.USED_DEVICE,
                source_record_id=payment.id,
                observed_at=now,
                confidence=1.0,
                source_type="DEVICE_FINGERPRINT",
                inferred=False,
            )
            self.store.upsert_edge(tenant_id, edge_dev)
            created_edges.append(edge_dev)

        # Customer -[USED_INSTRUMENT]-> PaymentInstrumentToken
        if card_token:
            v_card = GraphVertex(
                id=card_token,
                tenant_id=tenant_id,
                label=VertexLabel.PAYMENT_INSTRUMENT_TOKEN,
                properties={},
                is_tokenized=True,
                created_at=now,
            )
            self.store.upsert_vertex(tenant_id, v_card)

            edge_card = GraphEdge(
                id=f"edge_{uuid.uuid4().hex[:12]}",
                tenant_id=tenant_id,
                source_id=cust_token,
                target_id=card_token,
                label=EdgeLabel.USED_INSTRUMENT,
                source_record_id=payment.id,
                observed_at=now,
                confidence=1.0,
                source_type="PAYMENT_GATEWAY",
                inferred=False,
            )
            self.store.upsert_edge(tenant_id, edge_card)
            created_edges.append(edge_card)

        # Payment -[HAS_REFERENCE]-> UPIReferenceToken
        if upi_token:
            v_upi = GraphVertex(
                id=upi_token,
                tenant_id=tenant_id,
                label=VertexLabel.UPI_REFERENCE_TOKEN,
                properties={},
                is_tokenized=True,
                created_at=now,
            )
            self.store.upsert_vertex(tenant_id, v_upi)

            edge_upi = GraphEdge(
                id=f"edge_{uuid.uuid4().hex[:12]}",
                tenant_id=tenant_id,
                source_id=payment.id,
                target_id=upi_token,
                label=EdgeLabel.HAS_REFERENCE,
                source_record_id=payment.id,
                observed_at=now,
                confidence=1.0,
                source_type="BANK_UPI_RRN",
                inferred=False,
            )
            self.store.upsert_edge(tenant_id, edge_upi)
            created_edges.append(edge_upi)

        audit_service.record(
            tenant_id=tenant_id,
            actor_id=ctx.user_id,
            action="GRAPH_TRANSACTION_MATERIALIZED",
            resource_type="Payment",
            resource_id=payment.id,
            details={
                "customer_token": cust_token,
                "device_token": dev_token,
                "edges_created": len(created_edges),
            },
            correlation_id=correlation_id,
        )

        return {
            "payment_id": payment.id,
            "customer_token": cust_token,
            "device_token": dev_token,
            "card_token": card_token,
            "upi_token": upi_token,
            "edges_count": len(created_edges),
        }

    def link_case_to_graph(
        self,
        tenant_id: str,
        case_id: str,
        entity_token: str,
        reason: str = "FLAGGED_IN_CASE",
    ) -> GraphEdge:
        """Link an operational case to an entity vertex in the graph."""
        now = datetime.now(timezone.utc)
        v_case = GraphVertex(
            id=case_id,
            tenant_id=tenant_id,
            label=VertexLabel.CASE,
            properties={"flagged_at": now.isoformat()},
            is_tokenized=False,
            created_at=now,
        )
        self.store.upsert_vertex(tenant_id, v_case)

        edge = GraphEdge(
            id=f"edge_case_{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            source_id=entity_token,
            target_id=case_id,
            label=EdgeLabel.FLAGGED_IN_CASE,
            source_record_id=case_id,
            observed_at=now,
            confidence=1.0,
            source_type="ANALYST_INVESTIGATION",
            inferred=False,
            properties={"reason": reason},
        )
        self.store.upsert_edge(tenant_id, edge)
        return edge

    def query_neighborhood(
        self,
        ctx: TenantContext,
        entity_token: str,
        depth: int = 2,
        limit: int = 50,
    ) -> GraphNeighborhood:
        """Bounded graph traversal around an entity token within caller's tenant."""
        return self.store.query_neighborhood(
            tenant_id=ctx.tenant_id,
            entity_token=entity_token,
            depth=depth,
            limit=limit,
        )


graph_service = GraphService()
