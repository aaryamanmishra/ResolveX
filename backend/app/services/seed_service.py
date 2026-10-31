"""Synthetic Demo Data Seeder for ResolveX AI.

Seeds deterministic payment scenarios, reconciliation discrepancies, tokenized graph
relationships, and active cases into in-memory services on startup or on-demand.
"""

from datetime import datetime, timedelta, timezone

from backend.app.agents.workflow import investigation_runner
from backend.app.domain.case import Approval, Case
from backend.app.domain.enums import (
    ApprovalDecision,
    CaseStatus,
    CaseType,
    EvidenceSourceType,
    FraudSeverity,
    FundsStatus,
    PaymentStatus,
    RefundStatus,
    VerificationState,
)
from backend.app.domain.evidence import EvidenceAsset, EvidenceClaim
from backend.app.domain.findings import (
    InvestigationFinding,
    ModelMetadata,
    PaymentStateSummary,
    RecommendedNextStep,
    StructuredInvestigationResult,
)
from backend.app.domain.graph import (
    EdgeLabel,
    GraphEdge,
    GraphVertex,
    VertexLabel,
)
from backend.app.domain.payment import Payment, PaymentEvent, Refund
from backend.app.security.tokenization import Tokenizer
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service
from backend.app.services.evidence_service import evidence_service
from backend.app.services.graph_service import graph_service
from backend.app.services.payment_service import payment_service
from backend.app.services.reconciliation_service import (
    ReconciliationDiscrepancy,
    reconciliation_engine,
)

DEMO_TENANT_ID = "tenant_finops_01"
tokenizer = Tokenizer()


def seed_demo_data(tenant_id: str = DEMO_TENANT_ID) -> dict:
    """Populate services with deterministic test scenarios matching PRD §15.1 & §15.2."""
    now = datetime.now(timezone.utc)

    # 1. Seed Payments
    p1 = Payment(
        id="pay_scen_success_001",
        tenant_id=tenant_id,
        merchant_id="mch_cloudstore",
        order_ref="ORD-2026-101",
        provider="simulator",
        provider_payment_id="sim_pay_succ_101",
        amount_minor=249900,  # ₹2,499.00
        currency="INR",
        payment_status=PaymentStatus.SUCCEEDED,
        funds_status=FundsStatus.PROVIDER_CONFIRMED_CREDIT,
        created_at=now - timedelta(minutes=50),
        updated_at=now - timedelta(minutes=49),
    )
    p2 = Payment(
        id="pay_scen_pending_002",
        tenant_id=tenant_id,
        merchant_id="mch_cloudstore",
        order_ref="ORD-2026-102",
        provider="simulator",
        provider_payment_id="sim_pay_pend_102",
        amount_minor=125000,  # ₹1,250.00
        currency="INR",
        payment_status=PaymentStatus.PENDING,
        funds_status=FundsStatus.UNKNOWN,
        created_at=now - timedelta(minutes=30),
        updated_at=now - timedelta(minutes=30),
    )
    p3 = Payment(
        id="pay_scen_failed_003",
        tenant_id=tenant_id,
        merchant_id="mch_cloudstore",
        order_ref="ORD-2026-103",
        provider="simulator",
        provider_payment_id="sim_pay_fail_103",
        amount_minor=99900,  # ₹999.00
        currency="INR",
        payment_status=PaymentStatus.FAILED,
        funds_status=FundsStatus.NOT_REPORTED,
        created_at=now - timedelta(minutes=20),
        updated_at=now - timedelta(minutes=19),
    )
    p4 = Payment(
        id="pay_scen_mismatch_004",
        tenant_id=tenant_id,
        merchant_id="mch_cloudstore",
        order_ref="ORD-2026-104",
        provider="simulator",
        provider_payment_id="sim_pay_mis_104",
        amount_minor=450000,  # ₹4,500.00
        currency="INR",
        payment_status=PaymentStatus.FAILED,
        funds_status=FundsStatus.CUSTOMER_REPORTED_DEBIT,
        created_at=now - timedelta(minutes=15),
        updated_at=now - timedelta(minutes=14),
    )
    p5 = Payment(
        id="pay_scen_refund_007",
        tenant_id=tenant_id,
        merchant_id="mch_cloudstore",
        order_ref="ORD-2026-107",
        provider="simulator",
        provider_payment_id="sim_pay_ref_107",
        amount_minor=199900,
        currency="INR",
        payment_status=PaymentStatus.SUCCEEDED,
        funds_status=FundsStatus.PROVIDER_CONFIRMED_CREDIT,
        created_at=now - timedelta(days=10),
        updated_at=now - timedelta(days=10),
    )

    payments = [p1, p2, p3, p4, p5]
    for p in payments:
        payment_service._payments[(tenant_id, p.id)] = p
        payment_service._order_index[(tenant_id, p.order_ref)] = p.id
        payment_service._provider_payment_index[(p.provider, p.provider_payment_id)] = (
            tenant_id,
            p.id,
        )
        if p.id not in payment_service._timeline:
            payment_service._timeline[p.id] = []

    # Timeline events for success payment
    e1 = PaymentEvent(
        id="evt_succ_01",
        payment_id=p1.id,
        provider_event_id="prv_evt_succ_01",
        event_type="payment.authorized",
        raw_status="authorized",
        normalized_status=PaymentStatus.INITIATED,
        source="provider_webhook",
        event_time=p1.created_at,
        received_at=p1.created_at,
        payload_hash="hash_auth_succ_01",
        idempotency_key=f"{tenant_id}:simulator:prv_evt_succ_01",
    )
    e2 = PaymentEvent(
        id="evt_succ_02",
        payment_id=p1.id,
        provider_event_id="prv_evt_succ_02",
        event_type="payment.captured",
        raw_status="captured",
        normalized_status=PaymentStatus.SUCCEEDED,
        source="provider_webhook",
        event_time=p1.updated_at,
        received_at=p1.updated_at,
        payload_hash="hash_cap_succ_02",
        idempotency_key=f"{tenant_id}:simulator:prv_evt_succ_02",
    )
    payment_service._timeline[p1.id] = [e1, e2]

    # Delayed Refund
    ref_delayed = Refund(
        id="ref_scen_delay_001",
        payment_id=p5.id,
        provider_refund_id="sim_ref_107",
        amount_minor=199900,
        currency="INR",
        refund_status=RefundStatus.PENDING,
        requested_at=now - timedelta(days=8),
        updated_at=now - timedelta(days=8),
    )
    payment_service._refunds[(tenant_id, ref_delayed.id)] = ref_delayed

    # Add Reconciliation Exceptions
    disc1 = ReconciliationDiscrepancy(
        discrepancy_code="UNCONFIRMED_CUSTOMER_DEBIT",
        payment_id=p4.id,
        tenant_id=tenant_id,
        description=f"Customer reported debit on payment {p4.id} while gateway reports FAILED.",
        severity=FraudSeverity.MEDIUM,
        evidence_ids=(p4.id,),
        details={
            "order_ref": p4.order_ref,
            "provider_status": p4.payment_status.value,
            "funds_status": p4.funds_status.value,
            "amount_minor": p4.amount_minor,
        },
    )
    disc2 = ReconciliationDiscrepancy(
        discrepancy_code="REFUND_SLA_BREACH",
        payment_id=p5.id,
        tenant_id=tenant_id,
        description=f"Refund {ref_delayed.id} has been pending for 8 days, exceeding the 5-day SLA.",
        severity=FraudSeverity.MEDIUM,
        evidence_ids=(ref_delayed.id,),
        details={
            "refund_id": ref_delayed.id,
            "days_pending": 8,
            "sla_days": 5,
        },
    )
    reconciliation_engine.record_discrepancy(disc1)
    reconciliation_engine.record_discrepancy(disc2)

    # 2. Seed Graph Vertices and Edges
    # Shared Device Syndicate
    dev_token = "dev_imei_cluster_99"
    v_dev = GraphVertex(
        id=dev_token,
        tenant_id=tenant_id,
        label=VertexLabel.DEVICE_TOKEN,
        properties={"fingerprint_class": "mobile_android", "os_version": "14"},
    )
    graph_service.store.upsert_vertex(tenant_id, v_dev)

    for i in range(1, 5):
        cust_tok = f"cust_tok_synth_{i:03d}"
        v_cust = GraphVertex(
            id=cust_tok,
            tenant_id=tenant_id,
            label=VertexLabel.CUSTOMER_TOKEN,
            properties={"tier": "new_user", "customer_index": i},
        )
        edge = GraphEdge(
            id=f"edge_used_dev_{i}",
            tenant_id=tenant_id,
            source_id=cust_tok,
            target_id=dev_token,
            label=EdgeLabel.USED_DEVICE,
            source_record_id=f"pay_fraud_cluster_{i}",
            observed_at=now - timedelta(minutes=30 - i * 5),
        )
        graph_service.store.upsert_vertex(tenant_id, v_cust)
        graph_service.store.upsert_edge(tenant_id, edge)

    # Link p4 into graph as well
    v_p4 = GraphVertex(
        id=p4.id,
        tenant_id=tenant_id,
        label=VertexLabel.PAYMENT,
        properties={
            "amount_minor": p4.amount_minor,
            "currency": p4.currency,
            "status": p4.payment_status.value,
        },
    )
    edge_p4 = GraphEdge(
        id="edge_p4_initiated",
        tenant_id=tenant_id,
        source_id="cust_tok_synth_001",
        target_id=p4.id,
        label=EdgeLabel.INITIATED_BY,
        source_record_id=p4.id,
        observed_at=p4.created_at,
    )
    graph_service.store.upsert_vertex(tenant_id, v_p4)
    graph_service.store.upsert_edge(tenant_id, edge_p4)

    # Benign Household (2 users sharing family device)
    benign_dev = "dev_family_tablet_home"
    v_b_dev = GraphVertex(
        id=benign_dev,
        tenant_id=tenant_id,
        label=VertexLabel.DEVICE_TOKEN,
        properties={"fingerprint_class": "tablet_ios"},
    )
    graph_service.store.upsert_vertex(tenant_id, v_b_dev)
    for b_idx in (1, 2):
        b_tok = f"cust_family_member_{b_idx}"
        v_b_cust = GraphVertex(id=b_tok, tenant_id=tenant_id, label=VertexLabel.CUSTOMER_TOKEN)
        edge_b = GraphEdge(
            id=f"edge_benign_{b_idx}",
            tenant_id=tenant_id,
            source_id=b_tok,
            target_id=benign_dev,
            label=EdgeLabel.USED_DEVICE,
            source_record_id=f"pay_benign_{b_idx}",
            observed_at=now - timedelta(days=b_idx),
        )
        graph_service.store.upsert_vertex(tenant_id, v_b_cust)
        graph_service.store.upsert_edge(tenant_id, edge_b)

    # 3. Seed Cases
    case_mismatch = Case(
        id="case_mismatch_001",
        tenant_id=tenant_id,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Payer debited ₹4,500.00 for ORD-2026-104 but order failed",
        description="Customer submitted receipt showing ₹4,500.00 debited via UPI, but gateway reports FAILED.",
        linked_payment_ids=[p4.id],
        priority=FraudSeverity.MEDIUM,
        case_status=CaseStatus.REVIEW_REQUIRED,
        owner_id="usr_support_01",
        created_at=now - timedelta(minutes=14),
    )
    case_fraud_ring = Case(
        id="case_fraud_002",
        tenant_id=tenant_id,
        case_type=CaseType.FRAUD_INVESTIGATION,
        title="High velocity shared device ring detected (4 accounts on 1 device)",
        description="Automated graph policy rule SHARED_DEVICE_THRESHOLD_EXCEEDED fired across token dev_imei_cluster_99.",
        linked_payment_ids=["dev_imei_cluster_99", p4.id],
        priority=FraudSeverity.HIGH,
        case_status=CaseStatus.NEW,
        owner_id="usr_fraud_01",
        created_at=now - timedelta(minutes=10),
    )

    case_service._cases[(tenant_id, case_mismatch.id)] = case_mismatch
    case_service._cases[(tenant_id, case_fraud_ring.id)] = case_fraud_ring

    # Draft human approval for case mismatch
    appr1 = Approval(
        id="appr_demo_001",
        case_id=case_mismatch.id,
        tenant_id=tenant_id,
        action_draft={
            "action_type": "DRAFT_REFUND_ESCALATION",
            "amount_minor": 450000,
            "currency": "INR",
            "reason": "Customer reported debit on failed payment.",
        },
        requested_by="agent_workflow",
        decision=ApprovalDecision.PENDING,
        timestamp=now - timedelta(minutes=12),
    )
    case_service._approvals[(tenant_id, appr1.id)] = appr1

    # 4. Seed Evidence Asset & Extracted Claims
    evid1 = EvidenceAsset(
        id="evid_mismatch_001",
        tenant_id=tenant_id,
        case_id=case_mismatch.id,
        storage_key="evidence/receipt_ord_104.png",
        mime_type="image/png",
        file_size_bytes=1048576,
        content_hash="6a8c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b899",
        source_type=EvidenceSourceType.RECEIPT_IMAGE,
        scan_status="CLEAN",
        retention_until=now + timedelta(days=90),
        created_at=now - timedelta(minutes=13),
    )
    claim1 = EvidenceClaim(
        id="claim_mismatch_001",
        evidence_asset_id=evid1.id,
        field_name="amount_minor",
        candidate_value="450000",
        confidence=0.98,
        verification_state=VerificationState.USER_CONFIRMED,
        source_location={"box_2d": [120, 45, 160, 210], "page": 1},
        created_at=now - timedelta(minutes=13),
    )
    claim2 = EvidenceClaim(
        id="claim_mismatch_002",
        evidence_asset_id=evid1.id,
        field_name="utr",
        candidate_value="UPI987654321098",
        confidence=0.95,
        verification_state=VerificationState.USER_CONFIRMED,
        source_location={"box_2d": [180, 45, 210, 260], "page": 1},
        created_at=now - timedelta(minutes=13),
    )
    evidence_service._assets[(tenant_id, evid1.id)] = evid1
    evidence_service._claims[(tenant_id, claim1.id)] = claim1
    evidence_service._claims[(tenant_id, claim2.id)] = claim2
    evidence_service._asset_claim_index[(tenant_id, evid1.id)] = [claim1.id, claim2.id]
    evidence_service._case_index[(tenant_id, case_mismatch.id)] = [evid1.id]

    # Pre-seed Structured Findings for case_mismatch_001
    finding_mismatch = StructuredInvestigationResult(
        case_id=case_mismatch.id,
        track="payment_issue",
        summary=(
            "Reconciliation anomaly: Customer bank statement confirms ₹4,500.00 debit via UPI UTR "
            "UPI987654321098, but payment provider marks transaction as FAILED with unknown funds status."
        ),
        payment_state=PaymentStateSummary(
            normalized_status=PaymentStatus.FAILED,
            source="provider_webhook",
            as_of=now - timedelta(minutes=14),
        ),
        findings=[
            InvestigationFinding(
                code="DISCREPANCY_DEBIT_UNCONFIRMED",
                statement="Customer debit reported but provider failed to settle to merchant escrow.",
                evidence_ids=[p4.id, evid1.id, claim1.id],
                confidence=0.96,
                uncertainty="Provider banking partner webhook delayed or dropped.",
            )
        ],
        unknowns=[
            "Provider settlement batch reference not yet received.",
            "Acquiring bank clearing cycle status pending.",
        ],
        recommended_next_step=RecommendedNextStep(
            action="DRAFT_REFUND_ESCALATION",
            requires_human_approval=True,
            external_side_effect=True,
            action_payload={
                "refund_amount_minor": "450000",
                "target_account": "cust_tok_synth_001",
                "reason": "Unsettled customer debit confirmed via receipt claim.",
            },
        ),
        model_metadata=ModelMetadata(
            provider="gemini",
            model_id="gemini-2.5-flash",
            prompt_version="1.0.0",
            execution_time_ms=420,
        ),
    )
    investigation_runner._latest_findings[(tenant_id, case_mismatch.id)] = finding_mismatch

    # 5. Audit Events
    audit_service.record(
        tenant_id=tenant_id,
        actor_id="system_seeder",
        action="DEMO_SCENARIO_SEEDED",
        resource_type="Tenant",
        resource_id=tenant_id,
        details={"payments_count": 5, "cases_count": 2, "vertices_count": 8},
    )

    return {
        "status": "SUCCESS",
        "tenant_id": tenant_id,
        "payments_seeded": len(payments),
        "cases_seeded": 2,
        "graph_vertices_seeded": 8,
    }
