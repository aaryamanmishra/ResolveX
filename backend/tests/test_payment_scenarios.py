"""Tests for all 9 required payment and reconciliation scenarios from PRD §15.1.

1. Successful payment
2. Pending payment
3. Failed payment
4. Customer reports debit but provider unconfirmed (claim vs truth separation)
5. Duplicate webhook (idempotency deduplication)
6. Out-of-order webhook events (no state regression)
7. Refund pending and SLA delay detection
8. Amount mismatch reconciliation exception
9. Missing order mapping exception
10. Razorpay webhook signature verification and parsing
"""

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.domain.enums import FundsStatus, PaymentStatus, RefundStatus, UserRole
from backend.app.domain.payment import CreatePaymentRequest
from backend.app.main import app
from backend.app.providers.payment_provider import SimulatorPaymentProvider
from backend.app.providers.razorpay_provider import RazorpayPaymentProvider
from backend.app.security.auth import create_access_token
from backend.app.security.context import TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service
from backend.app.services.payment_service import payment_service
from backend.app.services.reconciliation_service import reconciliation_engine

client = TestClient(app)


def reset_services() -> None:
    payment_service.clear()
    reconciliation_engine.clear()
    audit_service.clear()
    case_service.clear()


def test_scenario_1_successful_payment() -> None:
    """PRD Scenario 1: Successful payment updates normalized status and timeline."""
    reset_services()
    ctx = TenantContext(
        tenant_id="tenant_finops_01", user_id="usr_01", role=UserRole.SUPPORT_ANALYST
    )

    # 1. Create payment
    req = CreatePaymentRequest(
        tenant_id="tenant_finops_01",
        merchant_id="mch_01",
        order_ref="ORD-2026-SCEN1",
        amount_minor=299900,  # INR 2,999.00
        currency="INR",
        customer_token="cust_tok_01",
    )
    payment = payment_service.create_payment(ctx, req)
    assert payment.payment_status == PaymentStatus.CREATED

    # 2. Ingest signed success webhook from simulator
    sim = SimulatorPaymentProvider()
    payload = json.dumps(
        {
            "event_id": "evt_scen1_succ",
            "event_type": "payment.captured",
            "payment_id": payment.provider_payment_id,
            "order_ref": payment.order_ref,
            "amount_minor": 299900,
            "currency": "INR",
            "status": "succeeded",
        }
    ).encode("utf-8")
    sig = sim.generate_signature(payload)

    res = payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=payload,
        headers={"X-Simulator-Signature": sig},
        tenant_id="tenant_finops_01",
    )
    assert res.status == "PROCESSED"
    assert res.normalized_status == PaymentStatus.SUCCEEDED

    # Verify updated payment state
    updated = payment_service.get_payment(ctx, payment.id)
    assert updated.payment_status == PaymentStatus.SUCCEEDED
    assert updated.funds_status == FundsStatus.PROVIDER_CONFIRMED_CREDIT

    # Verify append-only timeline
    timeline = payment_service.get_timeline(ctx, payment.id)
    assert len(timeline) == 1
    assert timeline[0].normalized_status == PaymentStatus.SUCCEEDED


def test_scenario_2_pending_payment() -> None:
    """PRD Scenario 2: Pending payment remains pending without terminal status."""
    reset_services()
    ctx = TenantContext(
        tenant_id="tenant_finops_01", user_id="usr_01", role=UserRole.SUPPORT_ANALYST
    )

    req = CreatePaymentRequest(
        tenant_id="tenant_finops_01",
        merchant_id="mch_01",
        order_ref="ORD-2026-SCEN2",
        amount_minor=150000,
        currency="INR",
        customer_token="cust_tok_02",
    )
    payment = payment_service.create_payment(ctx, req)

    sim = SimulatorPaymentProvider()
    payload = json.dumps(
        {
            "event_id": "evt_scen2_pending",
            "event_type": "payment.created",
            "payment_id": payment.provider_payment_id,
            "order_ref": payment.order_ref,
            "amount_minor": 150000,
            "status": "pending",
        }
    ).encode("utf-8")
    sig = sim.generate_signature(payload)

    res = payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=payload,
        headers={"X-Simulator-Signature": sig},
        tenant_id="tenant_finops_01",
    )
    assert res.normalized_status == PaymentStatus.PENDING

    current = payment_service.get_payment(ctx, payment.id)
    assert current.payment_status == PaymentStatus.PENDING
    assert current.funds_status == FundsStatus.NOT_REPORTED


def test_scenario_3_failed_payment() -> None:
    """PRD Scenario 3: Provider failure webhook updates normalized status to FAILED."""
    reset_services()
    ctx = TenantContext(
        tenant_id="tenant_finops_01", user_id="usr_01", role=UserRole.SUPPORT_ANALYST
    )

    req = CreatePaymentRequest(
        tenant_id="tenant_finops_01",
        merchant_id="mch_01",
        order_ref="ORD-2026-SCEN3",
        amount_minor=50000,
        currency="INR",
        customer_token="cust_tok_03",
    )
    payment = payment_service.create_payment(ctx, req)

    sim = SimulatorPaymentProvider()
    payload = json.dumps(
        {
            "event_id": "evt_scen3_fail",
            "event_type": "payment.failed",
            "payment_id": payment.provider_payment_id,
            "order_ref": payment.order_ref,
            "amount_minor": 50000,
            "status": "failed",
        }
    ).encode("utf-8")
    sig = sim.generate_signature(payload)

    res = payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=payload,
        headers={"X-Simulator-Signature": sig},
        tenant_id="tenant_finops_01",
    )
    assert res.normalized_status == PaymentStatus.FAILED

    current = payment_service.get_payment(ctx, payment.id)
    assert current.payment_status == PaymentStatus.FAILED


def test_scenario_4_customer_reports_debit_mismatch() -> None:
    """PRD Scenario 4: Customer claims debit, but gateway reports FAILED.

    Core Safety Rule: Payer claim sets funds_status=CUSTOMER_REPORTED_DEBIT,
    does NOT overwrite payment_status, and triggers reconciliation exception.
    """
    reset_services()
    ctx = TenantContext(tenant_id="tenant_finops_01", user_id="usr_cust_01", role=UserRole.CUSTOMER)

    req = CreatePaymentRequest(
        tenant_id="tenant_finops_01",
        merchant_id="mch_01",
        order_ref="ORD-2026-SCEN4",
        amount_minor=450000,
        currency="INR",
        customer_token="cust_tok_04",
    )
    payment = payment_service.create_payment(ctx, req)

    # Ingest gateway failed webhook
    sim = SimulatorPaymentProvider()
    payload = json.dumps(
        {
            "event_id": "evt_scen4_fail",
            "event_type": "payment.failed",
            "payment_id": payment.provider_payment_id,
            "order_ref": payment.order_ref,
            "amount_minor": 450000,
            "status": "failed",
        }
    ).encode("utf-8")
    payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=payload,
        headers={"X-Simulator-Signature": sim.generate_signature(payload)},
        tenant_id="tenant_finops_01",
    )

    # Customer reports debit via API
    updated = payment_service.report_customer_debit(ctx, payment.id)

    # Authoritative provider status remains FAILED; funds_status reflects claim
    assert updated.payment_status == PaymentStatus.FAILED
    assert updated.funds_status == FundsStatus.CUSTOMER_REPORTED_DEBIT

    # Reconciliation engine raised exception
    exceptions = reconciliation_engine.list_exceptions("tenant_finops_01")
    assert any(ex.discrepancy_code == "DEBIT_REPORTED_PROVIDER_UNCONFIRMED" for ex in exceptions)


def test_scenario_5_duplicate_webhook() -> None:
    """PRD Scenario 5: Duplicate webhook suppressed via idempotency key without duplicate mutation."""
    reset_services()
    ctx = TenantContext(
        tenant_id="tenant_finops_01", user_id="usr_01", role=UserRole.SUPPORT_ANALYST
    )

    req = CreatePaymentRequest(
        tenant_id="tenant_finops_01",
        merchant_id="mch_01",
        order_ref="ORD-2026-SCEN5",
        amount_minor=100000,
        currency="INR",
        customer_token="cust_tok_05",
    )
    payment = payment_service.create_payment(ctx, req)

    sim = SimulatorPaymentProvider()
    payload = json.dumps(
        {
            "event_id": "evt_scen5_duplicate_id",
            "event_type": "payment.captured",
            "payment_id": payment.provider_payment_id,
            "order_ref": payment.order_ref,
            "amount_minor": 100000,
            "status": "succeeded",
        }
    ).encode("utf-8")
    sig = sim.generate_signature(payload)

    # First delivery
    res1 = payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=payload,
        headers={"X-Simulator-Signature": sig},
        tenant_id="tenant_finops_01",
    )
    assert res1.is_duplicate is False
    assert res1.status == "PROCESSED"

    # Second delivery with identical idempotency key
    res2 = payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=payload,
        headers={"X-Simulator-Signature": sig},
        tenant_id="tenant_finops_01",
    )
    assert res2.is_duplicate is True
    assert res2.status == "DUPLICATE_ACKNOWLEDGED"

    # Timeline only contains 1 event
    timeline = payment_service.get_timeline(ctx, payment.id)
    assert len(timeline) == 1


def test_scenario_6_out_of_order_events() -> None:
    """PRD Scenario 6: Out-of-order non-terminal event cannot regress a terminal SUCCEEDED status."""
    reset_services()
    ctx = TenantContext(
        tenant_id="tenant_finops_01", user_id="usr_01", role=UserRole.SUPPORT_ANALYST
    )

    req = CreatePaymentRequest(
        tenant_id="tenant_finops_01",
        merchant_id="mch_01",
        order_ref="ORD-2026-SCEN6",
        amount_minor=120000,
        currency="INR",
        customer_token="cust_tok_06",
    )
    payment = payment_service.create_payment(ctx, req)

    sim = SimulatorPaymentProvider()

    # 1. Terminal SUCCEEDED webhook arrives first
    succ_payload = json.dumps(
        {
            "event_id": "evt_scen6_captured",
            "event_type": "payment.captured",
            "payment_id": payment.provider_payment_id,
            "order_ref": payment.order_ref,
            "amount_minor": 120000,
            "status": "succeeded",
        }
    ).encode("utf-8")
    payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=succ_payload,
        headers={"X-Simulator-Signature": sim.generate_signature(succ_payload)},
        tenant_id="tenant_finops_01",
    )
    assert payment_service.get_payment(ctx, payment.id).payment_status == PaymentStatus.SUCCEEDED

    # 2. Delayed non-terminal INITIATED event arrives second
    delayed_init_payload = json.dumps(
        {
            "event_id": "evt_scen6_authorized_delayed",
            "event_type": "payment.authorized",
            "payment_id": payment.provider_payment_id,
            "order_ref": payment.order_ref,
            "amount_minor": 120000,
            "status": "initiated",
        }
    ).encode("utf-8")
    payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=delayed_init_payload,
        headers={"X-Simulator-Signature": sim.generate_signature(delayed_init_payload)},
        tenant_id="tenant_finops_01",
    )

    # Payment status remains SUCCEEDED without regression
    payment_after = payment_service.get_payment(ctx, payment.id)
    assert payment_after.payment_status == PaymentStatus.SUCCEEDED

    # Timeline recorded both events faithfully
    timeline = payment_service.get_timeline(ctx, payment.id)
    assert len(timeline) == 2


def test_scenario_7_refund_pending_and_sla_breach() -> None:
    """PRD Scenario 7: Refund in PENDING past 5 days SLA triggers reconciliation breach."""
    reset_services()
    ctx = TenantContext(
        tenant_id="tenant_finops_01", user_id="usr_01", role=UserRole.SUPPORT_ANALYST
    )

    req = CreatePaymentRequest(
        tenant_id="tenant_finops_01",
        merchant_id="mch_01",
        order_ref="ORD-2026-SCEN7",
        amount_minor=199900,
        currency="INR",
        customer_token="cust_tok_07",
    )
    payment = payment_service.create_payment(ctx, req)

    # Requested 8 days ago
    eight_days_ago = datetime.now(timezone.utc) - timedelta(days=8)
    refund = payment_service.record_refund(
        ctx=ctx,
        payment_id=payment.id,
        provider_refund_id="sim_ref_scen7",
        amount_minor=199900,
        status=RefundStatus.PENDING,
        requested_at=eight_days_ago,
    )
    assert refund.refund_status == RefundStatus.PENDING

    # SLA breach detected
    exceptions = reconciliation_engine.list_exceptions("tenant_finops_01")
    assert any(ex.discrepancy_code == "REFUND_SLA_BREACH" for ex in exceptions)


def test_scenario_8_amount_mismatch() -> None:
    """PRD Scenario 8: Provider amount differs from merchant order expected amount."""
    reset_services()
    ctx = TenantContext(
        tenant_id="tenant_finops_01", user_id="usr_01", role=UserRole.SUPPORT_ANALYST
    )

    req = CreatePaymentRequest(
        tenant_id="tenant_finops_01",
        merchant_id="mch_01",
        order_ref="ORD-2026-SCEN8",
        amount_minor=250000,  # Expected 2,500.00 INR
        currency="INR",
        customer_token="cust_tok_08",
    )
    payment = payment_service.create_payment(ctx, req)

    # Webhook arrives with 150000 minor units (mismatch)
    sim = SimulatorPaymentProvider()
    payload = json.dumps(
        {
            "event_id": "evt_scen8_mismatch",
            "event_type": "payment.captured",
            "payment_id": payment.provider_payment_id,
            "order_ref": payment.order_ref,
            "amount_minor": 150000,
            "status": "succeeded",
        }
    ).encode("utf-8")
    payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=payload,
        headers={"X-Simulator-Signature": sim.generate_signature(payload)},
        tenant_id="tenant_finops_01",
        expected_amount_minor=250000,  # Order expected 250000
    )

    exceptions = reconciliation_engine.list_exceptions("tenant_finops_01")
    mismatch_ex = next((ex for ex in exceptions if ex.discrepancy_code == "AMOUNT_MISMATCH"), None)
    assert mismatch_ex is not None
    assert mismatch_ex.details["expected_amount_minor"] == 250000
    assert mismatch_ex.details["provider_amount_minor"] == 150000


def test_scenario_9_missing_order_mapping() -> None:
    """PRD Scenario 9: Provider event arrives with missing or unknown order reference."""
    reset_services()

    sim = SimulatorPaymentProvider()
    payload = json.dumps(
        {
            "event_id": "evt_scen9_no_order",
            "event_type": "payment.captured",
            "payment_id": "sim_pay_orphan_99",
            "order_ref": "ORD-UNKNOWN",
            "amount_minor": 10000,
            "status": "succeeded",
        }
    ).encode("utf-8")
    payment_service.ingest_webhook(
        provider_name="simulator",
        raw_body=payload,
        headers={"X-Simulator-Signature": sim.generate_signature(payload)},
        tenant_id="tenant_finops_01",
    )

    exceptions = reconciliation_engine.list_exceptions("tenant_finops_01")
    assert any(ex.discrepancy_code == "MISSING_ORDER_MAPPING" for ex in exceptions)


def test_razorpay_webhook_signature_and_parsing() -> None:
    """Test Razorpay adapter signature generation, validation, and webhook parsing."""
    rzp = RazorpayPaymentProvider(webhook_secret="rzp_secret_test_key_123")
    body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_Kx9821h92k",
                        "amount": 499900,
                        "currency": "INR",
                        "status": "captured",
                        "order_id": "order_Kx87123",
                        "notes": {"order_ref": "ORD-RZP-TEST-99"},
                    }
                }
            },
        }
    ).encode("utf-8")

    sig = rzp.generate_signature(body)

    # Valid signature
    assert rzp.verify_webhook_signature(body, {"X-Razorpay-Signature": sig}) is True
    # Invalid signature fails
    assert rzp.verify_webhook_signature(body, {"X-Razorpay-Signature": "invalid_sig"}) is False

    # Parsing into canonical payload
    event_payload = rzp.parse_webhook_event(body, {"X-Razorpay-Signature": sig})
    assert event_payload.provider == "razorpay"
    assert event_payload.provider_payment_id == "pay_Kx9821h92k"
    assert event_payload.order_ref == "ORD-RZP-TEST-99"
    assert event_payload.amount_minor == 499900
    assert event_payload.normalized_status == PaymentStatus.SUCCEEDED


def test_payment_api_endpoints() -> None:
    """Test payment API endpoints for listing, retrieval, and webhook delivery."""
    reset_services()
    token = create_access_token(
        user_id="usr_support_01",
        tenant_id="tenant_finops_01",
        role=UserRole.SUPPORT_ANALYST,
        email="support@apex.example.com",
    )

    # 1. Create payment via API
    create_res = client.post(
        "/api/v1/payments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "tenant_id": "tenant_finops_01",
            "merchant_id": "mch_01",
            "order_ref": "ORD-API-TEST",
            "amount_minor": 75000,
            "currency": "INR",
            "customer_token": "cust_tok_api",
            "payment_method": "simulator",
        },
    )
    assert create_res.status_code == 201
    payment_id = create_res.json()["id"]

    # 2. Get payment detail
    get_res = client.get(
        f"/api/v1/payments/{payment_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["order_ref"] == "ORD-API-TEST"

    # 3. Deliver webhook via API endpoint
    sim = SimulatorPaymentProvider()
    webhook_body = json.dumps(
        {
            "event_id": "evt_api_succ",
            "event_type": "payment.captured",
            "payment_id": create_res.json()["provider_payment_id"],
            "order_ref": "ORD-API-TEST",
            "amount_minor": 75000,
            "status": "succeeded",
        }
    ).encode("utf-8")
    sig = sim.generate_signature(webhook_body)

    wh_res = client.post(
        "/api/v1/webhooks/simulator",
        content=webhook_body,
        headers={"X-Simulator-Signature": sig, "Content-Type": "application/json"},
    )
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "PROCESSED"
    assert wh_res.json()["normalized_status"] == "SUCCEEDED"

    # 4. Check timeline via API
    timeline_res = client.get(
        f"/api/v1/payments/{payment_id}/timeline",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert timeline_res.status_code == 200
    assert len(timeline_res.json()) == 1
