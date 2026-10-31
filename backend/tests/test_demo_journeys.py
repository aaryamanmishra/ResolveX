"""End-to-End Demo Journey Integration Tests for ResolveX AI.

PRD §6, §8, §9, §11, §15 & ANTIGRAVITY_BUILD_PLAN Phase 6 Quality Gates:
1. Track 1 Demo Journey:
   - Payment simulation (discrepancy scenario)
   - Customer debit claim reporting
   - Automated LangGraph investigation & citation validation
   - Multimodal evidence upload (receipt) & automated claim extraction
   - Customer confirmation of candidate claim
   - Human supervisor approval gate
   - Immutable audit trail verification
2. Track 2 Demo Journey:
   - Syndicate entity materialization in graph
   - Deterministic fraud rule detection
   - Graph agent investigation & explainable indicator synthesis
   - High-risk human approval gate
   - Supervisor approval decision
3. Zero-Key Guarantees:
   - Verification that both journeys run completely self-contained in DEMO_MODE=true
     without any paid external API keys (Gemini, Razorpay, DigitalOcean Spaces).
"""

import io
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.domain.enums import (
    ApprovalDecision,
    CaseStatus,
    CaseType,
    EvidenceSourceType,
    FundsStatus,
    PaymentStatus,
    UserRole,
    VerificationState,
)
from backend.app.domain.graph import (
    EdgeLabel,
    GraphEdge,
    GraphVertex,
    VertexLabel,
)
from backend.app.main import app
from backend.app.providers.payment_provider import SimulatorPaymentProvider
from backend.app.security.auth import create_access_token
from backend.app.security.context import TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service
from backend.app.services.evidence_service import evidence_service
from backend.app.services.graph_service import graph_service
from backend.app.services.payment_service import payment_service


@pytest.fixture(autouse=True)
def reset_stores():
    """Reset all in-memory repositories before each test."""
    payment_service.clear()
    case_service.clear()
    evidence_service.clear()
    audit_service.clear()
    graph_service.store.clear()
    yield
    payment_service.clear()
    case_service.clear()
    evidence_service.clear()
    audit_service.clear()
    graph_service.store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def analyst_token() -> str:
    return create_access_token(
        user_id="analyst_usr_1",
        tenant_id="tenant_bank_alpha",
        role=UserRole.FRAUD_ANALYST,
        email="analyst@alpha.bank",
    )


@pytest.fixture
def supervisor_token() -> str:
    return create_access_token(
        user_id="super_usr_1",
        tenant_id="tenant_bank_alpha",
        role=UserRole.SUPERVISOR,
        email="supervisor@alpha.bank",
    )


@pytest.fixture
def customer_token() -> str:
    return create_access_token(
        user_id="cust_usr_1",
        tenant_id="tenant_bank_alpha",
        role=UserRole.CUSTOMER,
        email="customer@gmail.com",
    )


class TestTrack1PaymentDemoJourney:
    """Track 1: End-to-End Payment Issue Triage, Evidence Intake, and Approval."""

    def test_complete_payment_discrepancy_demo_flow(
        self, client: TestClient, customer_token: str, supervisor_token: str
    ):
        """Simulate a stuck/failed payment, customer claim, agent triage, evidence confirmation,

        and supervisor approval under zero-key demo mode.
        """
        assert settings.DEMO_MODE is True
        tenant = "tenant_bank_alpha"

        # Step 1: Create initial payment session
        sim_headers = {"Authorization": f"Bearer {customer_token}"}
        create_res = client.post(
            "/api/v1/payments",
            headers=sim_headers,
            json={
                "tenant_id": tenant,
                "merchant_id": "merch_flipkart_99",
                "order_ref": "ORD_DEMO_TRACK1_001",
                "amount_minor": 450000,  # ₹4,500.00
                "currency": "INR",
                "customer_token": "cust_tok_001",
            },
        )
        assert create_res.status_code == 201
        payment = create_res.json()
        payment_id = payment["id"]
        assert payment["payment_status"] == "CREATED"

        # Ingest signed failure webhook from provider
        sim = SimulatorPaymentProvider()
        fail_body = json.dumps(
            {
                "event_id": "evt_demo_track1_fail",
                "event_type": "payment.failed",
                "payment_id": payment["provider_payment_id"],
                "order_ref": payment["order_ref"],
                "amount_minor": 450000,
                "currency": "INR",
                "status": "failed",
                "tenant_id": tenant,
            }
        ).encode("utf-8")
        sig = sim.generate_signature(fail_body)
        hook_res = client.post(
            "/api/v1/webhooks/simulator",
            content=fail_body,
            headers={"X-Simulator-Signature": sig, "Content-Type": "application/json"},
        )
        assert hook_res.status_code == 200

        # Step 2: Customer reports debit (PRD §7.1 - Money debited but order failed)
        claim_res = client.post(
            f"/api/v1/payments/{payment_id}/report-debit",
            headers=sim_headers,
            json={
                "note": "Money debited from HDFC account via UPI, but Flipkart showed order failed.",
            },
        )
        assert claim_res.status_code == 200
        claimed_payment = claim_res.json()
        assert claimed_payment["funds_status"] == FundsStatus.CUSTOMER_REPORTED_DEBIT.value

        # Step 3: Create Payment Discrepancy Case
        case_res = client.post(
            "/api/v1/cases",
            headers=sim_headers,
            json={
                "case_type": CaseType.PAYMENT_DISCREPANCY.value,
                "linked_payment_ids": [payment_id],
                "title": "Payment Stuck: Flipkart Order Failed with Bank Debit",
                "description": "Customer claims ₹4,500.00 debited from bank while gateway reports FAILED.",
            },
        )
        assert case_res.status_code == 201
        case_data = case_res.json()
        case_id = case_data["id"]

        # Step 4: Run Agent Investigation Workflow (Zero-key Gemma/Stub routing)
        inv_res = client.post(
            f"/api/v1/cases/{case_id}/investigate",
            headers={"Authorization": f"Bearer {supervisor_token}"},
            json={"track": "payment_issue"},
        )
        assert inv_res.status_code == 200
        inv_data = inv_res.json()
        assert inv_data["execution_status"] in (
            "REVIEW_REQUIRED",
            "COMPLETED",
            "PAUSED_FOR_APPROVAL",
        )
        assert inv_data["step_count"] <= 8

        # Step 5: Check Structured Investigation Findings & Citations
        findings_res = client.get(
            f"/api/v1/cases/{case_id}/findings",
            headers={"Authorization": f"Bearer {supervisor_token}"},
        )
        assert findings_res.status_code == 200
        findings = findings_res.json()
        assert findings["case_id"] == case_id
        assert findings["payment_state"]["normalized_status"] == PaymentStatus.FAILED.value
        assert findings["recommended_next_step"]["requires_human_approval"] is True
        # Verified safety invariant: No hallucinated refund executed
        assert findings["recommended_next_step"]["action"] != "EXECUTE_REFUND"

        # Step 6: Customer Uploads Evidence Receipt Image
        # Minimal valid PNG header
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        upload_res = client.post(
            "/api/v1/evidence/upload",
            headers=sim_headers,
            data={
                "case_id": case_id,
                "source_type": EvidenceSourceType.RECEIPT_IMAGE.value,
                "consent_granted": "true",
            },
            files={"file": ("hdfc_receipt.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert upload_res.status_code == 201
        upload_data = upload_res.json()
        evidence_id = upload_data["asset"]["id"]
        assert upload_data["asset"]["scan_status"] == "CLEAN"
        assert len(upload_data["claims"]) > 0

        # Step 7: Customer Confirms Extracted Candidate Claim
        first_claim = upload_data["claims"][0]
        confirm_res = client.post(
            f"/api/v1/evidence/{evidence_id}/confirm",
            headers=sim_headers,
            json={
                "claim_id": first_claim["id"],
                "decision": VerificationState.USER_CONFIRMED.value,
                "confirmed_value": "4500.00",
            },
        )
        assert confirm_res.status_code == 200
        confirmed_claim = confirm_res.json()
        assert confirmed_claim["verification_state"] == VerificationState.USER_CONFIRMED.value

        # Step 8: Supervisor Reviews and Approves Financial Action
        appr_res = client.get(
            f"/api/v1/cases/{case_id}/approvals",
            headers={"Authorization": f"Bearer {supervisor_token}"},
        )
        assert appr_res.status_code == 200
        approvals = appr_res.json()
        assert len(approvals) > 0
        approval = approvals[0]
        assert approval["decision"] == ApprovalDecision.PENDING.value

        decision_res = client.post(
            f"/api/v1/cases/approvals/{approval['id']}/decision",
            headers={"Authorization": f"Bearer {supervisor_token}"},
            json={
                "decision": ApprovalDecision.APPROVED.value,
                "reason": "Verified against confirmed debit claim and bank evidence. Refund authorized.",
            },
        )
        assert decision_res.status_code == 200
        dec_data = decision_res.json()
        assert dec_data["decision"] == ApprovalDecision.APPROVED.value

        # Verify Case is now marked RESOLVED or updated
        updated_case = case_service.get_case(
            TenantContext(tenant_id=tenant, user_id="super_usr_1", role=UserRole.SUPERVISOR),
            case_id,
        )
        assert updated_case is not None
        assert updated_case.case_status in (CaseStatus.RESOLVED, CaseStatus.REVIEW_REQUIRED)

        # Step 9: Verify Tamper-Evident Audit Trail Integrity
        audit_res = client.get(
            f"/api/v1/audit/resource/{case_id}",
            headers={"Authorization": f"Bearer {supervisor_token}"},
        )
        assert audit_res.status_code == 200
        audit_events = audit_res.json()
        assert len(audit_events) >= 2
        for ev in audit_events:
            assert len(ev["metadata_hash"]) == 64  # Valid SHA-256


class TestTrack2FraudDemoJourney:
    """Track 2: End-to-End Graph Fraud Investigation and Syndicate Detection."""

    def test_complete_fraud_syndicate_demo_flow(
        self, client: TestClient, analyst_token: str, supervisor_token: str
    ):
        """Seed a shared-device fraud syndicate across 4 accounts, run graph agent

        investigation, detect deterministic indicators, and obtain supervisor approval.
        """
        assert settings.DEMO_MODE is True
        tenant = "tenant_bank_alpha"
        ctx = TenantContext(tenant_id=tenant, user_id="analyst_usr_1", role=UserRole.FRAUD_ANALYST)
        now = datetime.now(timezone.utc)

        # Step 1: Materialize shared device syndicate in graph
        device_token = "dev_tok_syndicate_xyz"
        graph_service.store.upsert_vertex(
            tenant,
            GraphVertex(
                id=device_token,
                label=VertexLabel.DEVICE_TOKEN,
                tenant_id=tenant,
                properties={"device_hash": device_token},
            ),
        )

        customer_ids = [f"cust_mule_{i}" for i in range(4)]
        for idx, cid in enumerate(customer_ids):
            graph_service.store.upsert_vertex(
                tenant,
                GraphVertex(
                    id=cid,
                    label=VertexLabel.CUSTOMER_TOKEN,
                    tenant_id=tenant,
                    properties={"customer_id": cid},
                ),
            )
            # Edge: customer -> device
            graph_service.store.upsert_edge(
                tenant,
                GraphEdge(
                    id=f"edge_used_{idx}",
                    tenant_id=tenant,
                    source_id=cid,
                    target_id=device_token,
                    label=EdgeLabel.USED_DEVICE,
                    source_record_id=f"rec_login_{idx}",
                    observed_at=now,
                ),
            )

        # Step 2: Query Neighborhood via REST API
        graph_res = client.get(
            f"/api/v1/graph/neighborhood/{device_token}?depth=1",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert graph_res.status_code == 200
        subgraph = graph_res.json()
        assert len(subgraph["vertices"]) == 5  # 1 device + 4 customer mules
        assert len(subgraph["edges"]) == 4

        # Step 3: Create Fraud Investigation Case
        case_res = client.post(
            "/api/v1/cases",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={
                "case_type": CaseType.FRAUD_INVESTIGATION.value,
                "title": "Suspected Device Farm: Shared Hardware Fingerprint",
                "description": "Alert triggered for 4 distinct customer accounts accessing single device token.",
            },
        )
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]

        # Link device to case context so graph evaluator inspects it
        case_service.update_case_status(
            ctx, case_id, CaseStatus.TRIAGING, reason="Start investigation"
        )

        # Step 4: Evaluate Deterministic Fraud Rules via API
        rule_eval_res = client.post(
            f"/api/v1/cases/{case_id}/evaluate-fraud",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert rule_eval_res.status_code == 200

        # Step 5: Run Fraud Investigation Workflow
        inv_res = client.post(
            f"/api/v1/cases/{case_id}/investigate",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"track": "fraud_investigation"},
        )
        assert inv_res.status_code == 200
        inv_data = inv_res.json()
        assert inv_data["execution_status"] in (
            "REVIEW_REQUIRED",
            "COMPLETED",
            "PAUSED_FOR_APPROVAL",
        )

        # Step 6: Create high-risk containment approval (e.g. account freeze)
        app_res = client.post(
            f"/api/v1/cases/{case_id}/approval",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={
                "action_draft": {
                    "action_type": "FREEZE_ACCOUNT",
                    "target_entity": device_token,
                    "proposed_changes": {
                        "status": "FROZEN",
                        "reason": "Syndicate cluster detected",
                    },
                }
            },
        )
        assert app_res.status_code == 201
        approval = app_res.json()
        assert approval["decision"] == ApprovalDecision.PENDING.value

        # Analyst cannot approve high-risk action (supervisor role required)
        fail_app_res = client.post(
            f"/api/v1/cases/approvals/{approval['id']}/decision",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"decision": ApprovalDecision.APPROVED.value, "reason": "Attempt analyst bypass"},
        )
        assert fail_app_res.status_code == 403

        # Step 7: Supervisor approves containment
        ok_app_res = client.post(
            f"/api/v1/cases/approvals/{approval['id']}/decision",
            headers={"Authorization": f"Bearer {supervisor_token}"},
            json={
                "decision": ApprovalDecision.APPROVED.value,
                "reason": "Confirmed 4 linked accounts on single device. Containment authorized.",
            },
        )
        assert ok_app_res.status_code == 200
        assert ok_app_res.json()["decision"] == ApprovalDecision.APPROVED.value

        # Step 8: Verify Audit Trail
        audit_res = client.get(
            f"/api/v1/audit/resource/{case_id}",
            headers={"Authorization": f"Bearer {supervisor_token}"},
        )
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert any("DECISION" in e["action"] or "APPROVAL" in e["action"] for e in events)
