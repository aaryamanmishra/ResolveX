"""Synthetic Scenario Generator for ResolveX AI.

PRD §6 (FR-022), §15.1 & §15.2: Generates deterministic test fixtures covering
all required payment scenarios and fraud investigation topologies.
All data is strictly synthetic with no personal financial information.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure repository root is on sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.domain.case import Case, Merchant, Tenant, User
from backend.app.domain.enums import (
    CaseStatus,
    CaseType,
    EvidenceSourceType,
    FraudSeverity,
    FundsStatus,
    PaymentStatus,
    RefundStatus,
    UserRole,
    VerificationState,
)
from backend.app.domain.evidence import EvidenceAsset, EvidenceClaim
from backend.app.domain.graph import (
    EdgeLabel,
    GraphEdge,
    GraphVertex,
    VertexLabel,
)
from backend.app.domain.payment import Payment, PaymentEvent, Refund
from backend.app.security.tokenization import Tokenizer

DEMO_TENANT_ID = "tenant_finops_01"
tokenizer = Tokenizer()


def generate_synthetic_dataset() -> dict:
    """Generate complete deterministic scenario bundle."""
    base_time = datetime(2026, 10, 31, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Tenancy & Actors
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        name="Apex Payments Merchant Services",
        retention_days=90,
        settings={"fraud_shared_device_threshold": 3, "auto_triage": True},
    )

    support_user = User(
        id="usr_support_01",
        tenant_id=DEMO_TENANT_ID,
        role=UserRole.SUPPORT_ANALYST,
        email="support@apex.example.com",
        name="Ananya Sharma",
    )

    fraud_analyst = User(
        id="usr_fraud_01",
        tenant_id=DEMO_TENANT_ID,
        role=UserRole.FRAUD_ANALYST,
        email="fraud.analyst@apex.example.com",
        name="Vikram Sethi",
    )

    merchant = Merchant(
        id="mch_cloudstore",
        tenant_id=DEMO_TENANT_ID,
        external_ref="EXT-MCH-992",
        display_name="CloudRetail Store",
    )

    # 2. Payment Scenarios (PRD §15.1)

    # Scenario 1: Normal Success Payment
    pay_success = Payment(
        id="pay_scen_success_001",
        tenant_id=DEMO_TENANT_ID,
        merchant_id=merchant.id,
        order_ref="ORD-2026-101",
        provider="simulator",
        provider_payment_id="sim_pay_succ_101",
        amount_minor=249900,  # INR 2,499.00
        currency="INR",
        payment_status=PaymentStatus.SUCCEEDED,
        funds_status=FundsStatus.PROVIDER_CONFIRMED_CREDIT,
        created_at=base_time,
        updated_at=base_time + timedelta(seconds=12),
    )
    evt_succ_auth = PaymentEvent(
        id="evt_succ_01",
        payment_id=pay_success.id,
        provider_event_id="prv_evt_succ_01",
        event_type="payment.authorized",
        raw_status="authorized",
        normalized_status=PaymentStatus.INITIATED,
        source="provider_webhook",
        event_time=base_time + timedelta(seconds=5),
        received_at=base_time + timedelta(seconds=6),
        payload_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        idempotency_key=f"{DEMO_TENANT_ID}:simulator:prv_evt_succ_01",
    )
    evt_succ_cap = PaymentEvent(
        id="evt_succ_02",
        payment_id=pay_success.id,
        provider_event_id="prv_evt_succ_02",
        event_type="payment.captured",
        raw_status="captured",
        normalized_status=PaymentStatus.SUCCEEDED,
        source="provider_webhook",
        event_time=base_time + timedelta(seconds=12),
        received_at=base_time + timedelta(seconds=13),
        payload_hash="f4c0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b866",
        idempotency_key=f"{DEMO_TENANT_ID}:simulator:prv_evt_succ_02",
    )

    # Scenario 2: Pending Payment
    pay_pending = Payment(
        id="pay_scen_pending_002",
        tenant_id=DEMO_TENANT_ID,
        merchant_id=merchant.id,
        order_ref="ORD-2026-102",
        provider="simulator",
        provider_payment_id="sim_pay_pend_102",
        amount_minor=125000,  # INR 1,250.00
        currency="INR",
        payment_status=PaymentStatus.PENDING,
        funds_status=FundsStatus.UNKNOWN,
        created_at=base_time + timedelta(minutes=10),
        updated_at=base_time + timedelta(minutes=10),
    )

    # Scenario 3: Failed Payment
    pay_failed = Payment(
        id="pay_scen_failed_003",
        tenant_id=DEMO_TENANT_ID,
        merchant_id=merchant.id,
        order_ref="ORD-2026-103",
        provider="simulator",
        provider_payment_id="sim_pay_fail_103",
        amount_minor=99900,  # INR 999.00
        currency="INR",
        payment_status=PaymentStatus.FAILED,
        funds_status=FundsStatus.NOT_REPORTED,
        created_at=base_time + timedelta(minutes=15),
        updated_at=base_time + timedelta(minutes=15, seconds=30),
    )

    # Scenario 4: Customer Reports Debit but Gateway Shows Failed/Pending (Mismatch)
    pay_debit_mismatch = Payment(
        id="pay_scen_mismatch_004",
        tenant_id=DEMO_TENANT_ID,
        merchant_id=merchant.id,
        order_ref="ORD-2026-104",
        provider="simulator",
        provider_payment_id="sim_pay_mis_104",
        amount_minor=450000,  # INR 4,500.00
        currency="INR",
        payment_status=PaymentStatus.FAILED,
        funds_status=FundsStatus.CUSTOMER_REPORTED_DEBIT,  # Explicit separation
        created_at=base_time + timedelta(minutes=20),
        updated_at=base_time + timedelta(minutes=20, seconds=45),
    )
    evid_mismatch_receipt = EvidenceAsset(
        id="evid_mismatch_01",
        tenant_id=DEMO_TENANT_ID,
        case_id="case_mismatch_001",
        storage_key="evidence/receipt_ord_104.png",
        mime_type="image/png",
        file_size_bytes=1048576,
        content_hash="6a8c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b899",
        source_type=EvidenceSourceType.RECEIPT_IMAGE,
        scan_status="CLEAN",
        retention_until=base_time + timedelta(days=90),
        created_at=base_time + timedelta(minutes=25),
    )
    claim_debit_amount = EvidenceClaim(
        id="claim_mismatch_01",
        evidence_asset_id=evid_mismatch_receipt.id,
        field_name="amount_minor",
        candidate_value="450000",
        confidence=0.97,
        verification_state=VerificationState.USER_CONFIRMED,
        source_location={"box_2d": [120, 45, 160, 210], "page": 1},
        created_at=base_time + timedelta(minutes=26),
    )

    # Scenario 7: Refund Delayed
    pay_refund_delayed = Payment(
        id="pay_scen_refund_007",
        tenant_id=DEMO_TENANT_ID,
        merchant_id=merchant.id,
        order_ref="ORD-2026-107",
        provider="simulator",
        provider_payment_id="sim_pay_ref_107",
        amount_minor=199900,
        currency="INR",
        payment_status=PaymentStatus.SUCCEEDED,
        funds_status=FundsStatus.PROVIDER_CONFIRMED_CREDIT,
        created_at=base_time - timedelta(days=10),
    )
    ref_delayed = Refund(
        id="ref_scen_delay_001",
        payment_id=pay_refund_delayed.id,
        provider_refund_id="sim_ref_107",
        amount_minor=199900,
        currency="INR",
        refund_status=RefundStatus.PENDING,
        requested_at=base_time - timedelta(days=8),
        updated_at=base_time - timedelta(days=8),
    )

    # 3. Graph Fraud Scenarios (PRD §15.2)
    # Fraud Network: 4 distinct customer tokens sharing 1 device token (Above threshold of 3)
    dev_token = tokenizer.tokenize(DEMO_TENANT_ID, "device_fingerprint_imei_998822", prefix="dev")
    v_device = GraphVertex(
        id=dev_token,
        tenant_id=DEMO_TENANT_ID,
        label=VertexLabel.DEVICE_TOKEN,
        properties={"fingerprint_class": "mobile_android", "os_version": "14"},
        is_tokenized=True,
    )

    graph_vertices: list[GraphVertex] = [v_device]
    graph_edges: list[GraphEdge] = []

    for i in range(1, 5):
        cust_tok = tokenizer.tokenize(DEMO_TENANT_ID, f"customer_phone_987654321{i}", prefix="cust")
        v_cust = GraphVertex(
            id=cust_tok,
            tenant_id=DEMO_TENANT_ID,
            label=VertexLabel.CUSTOMER_TOKEN,
            properties={"tier": "new_user", "kyc_status": "minimal"},
            is_tokenized=True,
        )
        edge_used = GraphEdge(
            id=f"edge_used_dev_{i}",
            tenant_id=DEMO_TENANT_ID,
            source_id=cust_tok,
            target_id=dev_token,
            label=EdgeLabel.USED_DEVICE,
            source_record_id=f"pay_fraud_cluster_{i}",
            observed_at=base_time - timedelta(minutes=30 - i * 5),
            confidence=1.0,
            source_type="DEVICE_FINGERPRINT",
            inferred=False,
        )
        graph_vertices.append(v_cust)
        graph_edges.append(edge_used)

    # Benign Shared Device Scenario (Family Tablet, 2 users, below threshold)
    benign_dev = tokenizer.tokenize(DEMO_TENANT_ID, "family_ipad_tablet_home", prefix="dev")
    v_benign_dev = GraphVertex(
        id=benign_dev,
        tenant_id=DEMO_TENANT_ID,
        label=VertexLabel.DEVICE_TOKEN,
        properties={"fingerprint_class": "tablet_ios"},
        is_tokenized=True,
    )
    b_cust1 = tokenizer.tokenize(DEMO_TENANT_ID, "customer_family_member_1", prefix="cust")
    b_cust2 = tokenizer.tokenize(DEMO_TENANT_ID, "customer_family_member_2", prefix="cust")
    v_b_cust1 = GraphVertex(id=b_cust1, tenant_id=DEMO_TENANT_ID, label=VertexLabel.CUSTOMER_TOKEN)
    v_b_cust2 = GraphVertex(id=b_cust2, tenant_id=DEMO_TENANT_ID, label=VertexLabel.CUSTOMER_TOKEN)

    edge_b1 = GraphEdge(
        id="edge_benign_1",
        tenant_id=DEMO_TENANT_ID,
        source_id=b_cust1,
        target_id=benign_dev,
        label=EdgeLabel.USED_DEVICE,
        source_record_id="pay_benign_01",
        observed_at=base_time - timedelta(days=2),
    )
    edge_b2 = GraphEdge(
        id="edge_benign_2",
        tenant_id=DEMO_TENANT_ID,
        source_id=b_cust2,
        target_id=benign_dev,
        label=EdgeLabel.USED_DEVICE,
        source_record_id="pay_benign_02",
        observed_at=base_time - timedelta(days=1),
    )
    graph_vertices.extend([v_benign_dev, v_b_cust1, v_b_cust2])
    graph_edges.extend([edge_b1, edge_b2])

    # Sample Cases
    case_mismatch = Case(
        id="case_mismatch_001",
        tenant_id=DEMO_TENANT_ID,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Payer debited for ORD-2026-104 but order failed",
        description="Customer submitted screenshot showing INR 4,500.00 debited via UPI, but simulator shows failed event.",
        linked_payment_ids=[pay_debit_mismatch.id],
        priority=FraudSeverity.MEDIUM,
        case_status=CaseStatus.REVIEW_REQUIRED,
        owner_id=support_user.id,
    )

    case_fraud_ring = Case(
        id="case_fraud_002",
        tenant_id=DEMO_TENANT_ID,
        case_type=CaseType.FRAUD_INVESTIGATION,
        title="High velocity shared device ring detected (4 accounts on 1 device)",
        description="Automated graph policy rule SHARED_DEVICE_THRESHOLD_EXCEEDED fired.",
        linked_payment_ids=["pay_fraud_cluster_1", "pay_fraud_cluster_2"],
        priority=FraudSeverity.HIGH,
        case_status=CaseStatus.NEW,
        owner_id=fraud_analyst.id,
    )

    return {
        "tenant": tenant,
        "users": [support_user, fraud_analyst],
        "merchant": merchant,
        "payments": [pay_success, pay_pending, pay_failed, pay_debit_mismatch, pay_refund_delayed],
        "payment_events": [evt_succ_auth, evt_succ_cap],
        "refunds": [ref_delayed],
        "evidence_assets": [evid_mismatch_receipt],
        "evidence_claims": [claim_debit_amount],
        "cases": [case_mismatch, case_fraud_ring],
        "graph_vertices": graph_vertices,
        "graph_edges": graph_edges,
    }


if __name__ == "__main__":
    data = generate_synthetic_dataset()
    print("=== ResolveX Synthetic Seed Scenario Bundle ===")
    print(f"Tenant: {data['tenant'].name} ({data['tenant'].id})")
    print(f"Payments Seeded: {len(data['payments'])}")
    print(f"Payment Events Seeded: {len(data['payment_events'])}")
    print(f"Cases Seeded: {len(data['cases'])}")
    print(f"Graph Vertices: {len(data['graph_vertices'])}, Edges: {len(data['graph_edges'])}")
    print("Seed scenario generation successful.")
