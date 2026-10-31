"""Tests for all 6 required graph fraud investigation scenarios from PRD §15.2.

1. Multiple customer tokens share a device token above threshold (> 3) -> High severity fraud syndicate.
2. Repeated low-value attempts across multiple payment instruments (card testing / smurfing).
3. High transaction velocity burst for a tokenized entity.
4. Flagged payment connects to a previously reviewed historical fraud case -> Critical severity.
5. Benign shared-device scenario -> Automated alert suppressed, does not become an automatic fraud verdict.
6. Bounded graph traversal -> depth bounded between 1 and 4, max limit enforced.
7. Tenant isolation -> Cross-tenant graph traversals strictly return empty or fail closed.
8. Apache AGE Cypher query builder -> Valid openCypher SQL syntax.
9. Graph API endpoints -> REST query and evaluation.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.domain.case import Case
from backend.app.domain.enums import CaseType, FraudSeverity, PaymentStatus, UserRole
from backend.app.domain.graph import (
    EdgeLabel,
    GraphEdge,
    GraphVertex,
    VertexLabel,
)
from backend.app.domain.payment import Payment
from backend.app.graph.age_adapter import ApacheAGEGraphStore
from backend.app.graph.graph_store import MemoryGraphStore
from backend.app.main import app
from backend.app.policies.fraud_rules import DeterministicFraudRuleEngine
from backend.app.security.auth import create_access_token
from backend.app.security.context import TenantContext
from backend.app.services.case_service import case_service
from backend.app.services.graph_service import graph_service

client = TestClient(app)


def test_fraud_scenario_1_shared_device_syndicate() -> None:
    """PRD Scenario 1: > 3 customer tokens share 1 device token -> Fraud Syndicate."""
    store = MemoryGraphStore()
    rule_engine = DeterministicFraudRuleEngine()
    now = datetime.now(timezone.utc)
    tenant_id = "tenant_finops_01"

    # Seed 1 device token
    dev_token = "dev_imei_cluster_99"
    v_dev = GraphVertex(id=dev_token, tenant_id=tenant_id, label=VertexLabel.DEVICE_TOKEN)
    store.upsert_vertex(tenant_id, v_dev)

    # Seed 4 distinct customer tokens connected to this device (> threshold of 3)
    for i in range(1, 5):
        cust_id = f"cust_user_{i}"
        v_cust = GraphVertex(id=cust_id, tenant_id=tenant_id, label=VertexLabel.CUSTOMER_TOKEN)
        store.upsert_vertex(tenant_id, v_cust)

        edge = GraphEdge(
            id=f"e_used_{i}",
            tenant_id=tenant_id,
            source_id=cust_id,
            target_id=dev_token,
            label=EdgeLabel.USED_DEVICE,
            source_record_id=f"pay_src_{i}",
            observed_at=now,
        )
        store.upsert_edge(tenant_id, edge)

    # Query neighborhood
    neighborhood = store.query_neighborhood(tenant_id, dev_token, depth=2)
    assert neighborhood.total_nodes == 5
    assert neighborhood.total_edges == 4

    # Evaluate deterministic fraud rules
    result = rule_engine.evaluate_neighborhood("case_syndicate_01", neighborhood)
    assert result.is_alert is True
    assert result.severity == FraudSeverity.HIGH
    assert "SHARED_DEVICE_THRESHOLD_EXCEEDED" in result.reason_codes
    assert result.requires_human_review is True
    assert dev_token in result.evidence_ids
    assert "cust_user_1" in result.evidence_ids


def test_fraud_scenario_2_repeated_low_value_multi_instruments() -> None:
    """PRD Scenario 2: Customer connected to >= 3 payment instruments (card testing)."""
    store = MemoryGraphStore()
    rule_engine = DeterministicFraudRuleEngine()
    now = datetime.now(timezone.utc)
    tenant_id = "tenant_finops_01"

    cust_token = "cust_smurfer_01"
    v_cust = GraphVertex(id=cust_token, tenant_id=tenant_id, label=VertexLabel.CUSTOMER_TOKEN)
    store.upsert_vertex(tenant_id, v_cust)

    # Seed 3 distinct payment cards/instruments
    for i in range(1, 4):
        card_id = f"inst_card_token_{i}"
        v_card = GraphVertex(
            id=card_id, tenant_id=tenant_id, label=VertexLabel.PAYMENT_INSTRUMENT_TOKEN
        )
        store.upsert_vertex(tenant_id, v_card)

        edge = GraphEdge(
            id=f"e_card_{i}",
            tenant_id=tenant_id,
            source_id=cust_token,
            target_id=card_id,
            label=EdgeLabel.USED_INSTRUMENT,
            source_record_id=f"pay_inst_{i}",
            observed_at=now,
        )
        store.upsert_edge(tenant_id, edge)

    neighborhood = store.query_neighborhood(tenant_id, cust_token, depth=2)
    result = rule_engine.evaluate_neighborhood("case_card_test_01", neighborhood)

    assert result.is_alert is True
    assert result.severity == FraudSeverity.HIGH
    assert "REPEATED_ATTEMPTS_MULTI_INSTRUMENTS" in result.reason_codes


def test_fraud_scenario_3_high_transaction_velocity() -> None:
    """PRD Scenario 3: High transaction velocity burst (>= 4 payments)."""
    store = MemoryGraphStore()
    rule_engine = DeterministicFraudRuleEngine()
    now = datetime.now(timezone.utc)
    tenant_id = "tenant_finops_01"

    cust_token = "cust_burst_01"
    store.upsert_vertex(
        tenant_id, GraphVertex(id=cust_token, tenant_id=tenant_id, label=VertexLabel.CUSTOMER_TOKEN)
    )

    # 4 transactions
    for i in range(1, 5):
        pay_id = f"pay_burst_{i}"
        store.upsert_vertex(
            tenant_id, GraphVertex(id=pay_id, tenant_id=tenant_id, label=VertexLabel.PAYMENT)
        )
        store.upsert_edge(
            tenant_id,
            GraphEdge(
                id=f"e_pay_{i}",
                tenant_id=tenant_id,
                source_id=cust_token,
                target_id=pay_id,
                label=EdgeLabel.INITIATED_BY,
                source_record_id=pay_id,
                observed_at=now,
            ),
        )

    neighborhood = store.query_neighborhood(tenant_id, cust_token, depth=2)
    result = rule_engine.evaluate_neighborhood("case_burst_01", neighborhood)

    assert result.is_alert is True
    assert result.severity == FraudSeverity.MEDIUM
    assert "UNUSUAL_TRANSACTION_VELOCITY" in result.reason_codes


def test_fraud_scenario_4_link_to_prior_fraud_case() -> None:
    """PRD Scenario 4: Flagged payment connects to previously confirmed fraud case."""
    store = MemoryGraphStore()
    rule_engine = DeterministicFraudRuleEngine()
    now = datetime.now(timezone.utc)
    tenant_id = "tenant_finops_01"

    dev_token = "dev_shared_recidivist"
    store.upsert_vertex(
        tenant_id, GraphVertex(id=dev_token, tenant_id=tenant_id, label=VertexLabel.DEVICE_TOKEN)
    )

    # Link to historical confirmed fraud case
    prior_case_id = "case_confirmed_syndicate_2025"
    store.upsert_vertex(
        tenant_id, GraphVertex(id=prior_case_id, tenant_id=tenant_id, label=VertexLabel.CASE)
    )
    store.upsert_edge(
        tenant_id,
        GraphEdge(
            id="e_prior_case",
            tenant_id=tenant_id,
            source_id=dev_token,
            target_id=prior_case_id,
            label=EdgeLabel.FLAGGED_IN_CASE,
            source_record_id=prior_case_id,
            observed_at=now,
        ),
    )

    neighborhood = store.query_neighborhood(tenant_id, dev_token, depth=2)
    result = rule_engine.evaluate_neighborhood("case_new_investigation_01", neighborhood)

    assert result.is_alert is True
    assert result.severity == FraudSeverity.CRITICAL
    assert "CONNECTED_TO_HISTORICAL_FRAUD_CASE" in result.reason_codes
    assert prior_case_id in result.evidence_ids


def test_fraud_scenario_5_benign_shared_device_false_positive_prevention() -> None:
    """PRD Scenario 5: Benign shared device (Family Tablet, 2 users).

    GATE REQUIREMENT: Must NOT become an automatic fraud verdict.
    """
    store = MemoryGraphStore()
    rule_engine = DeterministicFraudRuleEngine()
    now = datetime.now(timezone.utc)
    tenant_id = "tenant_finops_01"

    dev_token = "dev_family_ipad_tablet"
    v_dev = GraphVertex(id=dev_token, tenant_id=tenant_id, label=VertexLabel.DEVICE_TOKEN)
    store.upsert_vertex(tenant_id, v_dev)

    # Only 2 accounts (e.g. parent and child) sharing the device
    for i in (1, 2):
        cust_id = f"cust_family_{i}"
        store.upsert_vertex(
            tenant_id,
            GraphVertex(id=cust_id, tenant_id=tenant_id, label=VertexLabel.CUSTOMER_TOKEN),
        )
        store.upsert_edge(
            tenant_id,
            GraphEdge(
                id=f"e_fam_{i}",
                tenant_id=tenant_id,
                source_id=cust_id,
                target_id=dev_token,
                label=EdgeLabel.USED_DEVICE,
                source_record_id=f"pay_fam_{i}",
                observed_at=now,
            ),
        )

    neighborhood = store.query_neighborhood(tenant_id, dev_token, depth=2)
    result = rule_engine.evaluate_neighborhood("case_benign_01", neighborhood)

    # Core Gate Check: NO automated fraud alert, severity is NONE
    assert result.is_alert is False
    assert result.severity == FraudSeverity.NONE
    assert result.requires_human_review is False
    assert any(m.rule_name == "BENIGN_SHARED_DEVICE_FILTER" for m in result.matched_rules)


def test_fraud_scenario_6_bounded_traversal() -> None:
    """PRD §7.3: Traversals are strictly bounded by depth (max 4) and node limits."""
    store = MemoryGraphStore()
    now = datetime.now(timezone.utc)
    tenant_id = "tenant_finops_01"

    # Create a long 6-hop chain
    for i in range(1, 8):
        v = GraphVertex(id=f"node_{i}", tenant_id=tenant_id, label=VertexLabel.CUSTOMER_TOKEN)
        store.upsert_vertex(tenant_id, v)
        if i > 1:
            edge = GraphEdge(
                id=f"e_chain_{i}",
                tenant_id=tenant_id,
                source_id=f"node_{i - 1}",
                target_id=f"node_{i}",
                label=EdgeLabel.SAME_TOKEN_AS,
                source_record_id=f"rec_{i}",
                observed_at=now,
            )
            store.upsert_edge(tenant_id, edge)

    # Search with depth=2 bounded
    nb_2 = store.query_neighborhood(tenant_id, "node_1", depth=2)
    assert nb_2.depth == 2
    assert nb_2.total_nodes == 3  # node_1, node_2, node_3

    # Attempt depth=10 -> Must be clamped to max 4
    nb_clamped = store.query_neighborhood(tenant_id, "node_1", depth=10)
    assert nb_clamped.depth == 4
    assert nb_clamped.total_nodes <= 5


def test_graph_tenant_isolation() -> None:
    """PRD §6 (FR-002): Cross-tenant graph traversals strictly return empty."""
    store = MemoryGraphStore()

    # Seed node in Tenant A
    store.upsert_vertex(
        "tenant_a",
        GraphVertex(id="node_secret_a", tenant_id="tenant_a", label=VertexLabel.CUSTOMER_TOKEN),
    )

    # Tenant B tries to query Tenant A's node -> returns empty
    nb_b = store.query_neighborhood("tenant_b", "node_secret_a", depth=2)
    assert nb_b.total_nodes == 0
    assert len(nb_b.vertices) == 0


def test_apache_age_cypher_builder() -> None:
    """Verifies openCypher query generator for Apache AGE compliance."""
    age_store = ApacheAGEGraphStore(graph_name="resolvex_fraud_graph")

    # Vertex cypher
    vertex = GraphVertex(
        id="cust_test_token_123",
        tenant_id="tenant_finops_01",
        label=VertexLabel.CUSTOMER_TOKEN,
        properties={"tier": "vip"},
    )
    v_cypher = age_store.build_create_vertex_cypher(vertex)
    assert "MERGE (v:CustomerToken" in v_cypher.cypher_text
    assert "SELECT * FROM cypher('resolvex_fraud_graph'" in v_cypher.sql_wrapper

    # Edge cypher
    edge = GraphEdge(
        id="e_test_99",
        tenant_id="tenant_finops_01",
        source_id="cust_test_token_123",
        target_id="dev_test_456",
        label=EdgeLabel.USED_DEVICE,
        source_record_id="pay_99",
        observed_at=datetime.now(timezone.utc),
    )
    e_cypher = age_store.build_create_edge_cypher(edge)
    assert "MERGE (s)-[r:USED_DEVICE" in e_cypher.cypher_text

    # Path traversal cypher
    p_cypher = age_store.build_neighborhood_cypher(
        "tenant_finops_01", "cust_test_token_123", depth=2
    )
    assert "[*1..2]" in p_cypher.cypher_text


def test_graph_and_fraud_evaluation_api_endpoints() -> None:
    """Test REST API endpoints for graph neighborhood and deterministic fraud evaluation."""
    case_service.clear()

    # 1. Setup Case and Tokenized Graph in GraphService
    analyst_token = create_access_token(
        user_id="usr_fraud_01",
        tenant_id="tenant_finops_01",
        role=UserRole.FRAUD_ANALYST,
        email="fraud.analyst@apex.example.com",
    )

    ctx = TenantContext(
        tenant_id="tenant_finops_01", user_id="usr_fraud_01", role=UserRole.FRAUD_ANALYST
    )
    case = case_service.create_case(
        ctx=ctx,
        case_type=CaseType.FRAUD_INVESTIGATION,
        title="Investigation on high risk device cluster",
        priority=FraudSeverity.LOW,
    )

    # Materialize transaction using graph service
    dummy_payment = Payment(
        id="pay_graph_test_01",
        tenant_id="tenant_finops_01",
        merchant_id="mch_cloudstore",
        order_ref="ORD-GRAPH-01",
        provider="simulator",
        provider_payment_id="sim_pay_g01",
        amount_minor=120000,
        currency="INR",
        payment_status=PaymentStatus.SUCCEEDED,
    )
    mat_result = graph_service.materialize_transaction(
        ctx=ctx,
        payment=dummy_payment,
        raw_customer_id="customer_phone_9911223344",
        raw_device_id="device_imei_99118822",
    )
    cust_token = mat_result["customer_token"]

    # Link payment to case
    case_service._cases[(ctx.tenant_id, case.id)] = Case(
        id=case.id,
        tenant_id=case.tenant_id,
        case_type=case.case_type,
        title=case.title,
        description=case.description,
        linked_payment_ids=[dummy_payment.id],
        priority=case.priority,
        case_status=case.case_status,
        owner_id=case.owner_id,
    )

    # 2. Query neighborhood via API
    nb_res = client.get(
        f"/api/v1/graph/neighborhood/{cust_token}?depth=2",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert nb_res.status_code == 200
    nb_data = nb_res.json()
    assert nb_data["center_vertex_id"] == cust_token
    assert nb_data["total_nodes"] >= 2

    # 3. Evaluate fraud rules on case via API
    eval_res = client.post(
        f"/api/v1/cases/{case.id}/evaluate-fraud?depth=2",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["case_id"] == case.id
    assert "is_alert" in eval_data
    assert "requires_human_review" in eval_data
