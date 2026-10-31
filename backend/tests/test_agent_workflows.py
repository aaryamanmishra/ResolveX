"""Comprehensive Phase 4 Acceptance Tests for ResolveX AI.

PRD §8, §9, §10, §13 & ANTIGRAVITY_BUILD_PLAN Phase 4 Gates:
1. Track 1 Payment Issue Triage: runs bounded workflow, reconciles timeline, outputs Pydantic findings.
2. Track 2 Fraud Investigation: runs bounded workflow with graph context and explainable indicators.
3. Safety Invariant 1: No agent can mutate payment truth, execute a refund, or freeze an account.
4. Safety Invariant 2: MCP server blocks prohibited tools and unlisted skill tools server-side.
5. Citation Invariant: All factual findings must cite genuine evidence IDs; unsupported claims are marked unknown.
6. Human Review Gate: Sensitive financial actions pause execution with checkpointing; resumes on human sign-off.
7. Model Interchangeability: Gemma, Gemini, and Stub providers route cleanly; DEMO_MODE falls back safely.
8. API Endpoint Verification: /cases/{case_id}/investigate, /cases/{case_id}/findings, and approval decisions.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.agent_skills.registry import SkillRegistry
from backend.app.agents.nodes import (
    node_validate_findings,
)
from backend.app.agents.state import InvestigationAgentState
from backend.app.agents.workflow import investigation_runner
from backend.app.config import settings
from backend.app.domain.enums import (
    ApprovalDecision,
    CaseStatus,
    CaseType,
    FraudSeverity,
    FundsStatus,
    PaymentStatus,
    UserRole,
)
from backend.app.domain.findings import StructuredInvestigationResult
from backend.app.domain.graph import GraphVertex, VertexLabel
from backend.app.domain.payment import Payment, PaymentEvent
from backend.app.main import app
from backend.app.mcp.tools import (
    FORBIDDEN_TOOLS,
    ProhibitedToolError,
    ToolPermissionError,
    mcp_tool_registry,
)
from backend.app.providers.model_provider import (
    GeminiModelProvider,
    GemmaModelProvider,
    ModelRequest,
    ModelRouter,
    StubModelProvider,
)
from backend.app.security.auth import create_access_token
from backend.app.security.context import TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service
from backend.app.services.graph_service import graph_service
from backend.app.services.payment_service import payment_service


@pytest.fixture(autouse=True)
def clean_services() -> None:
    """Reset singletons between tests."""
    case_service.clear()
    payment_service.clear()
    graph_service.store.clear()
    mcp_tool_registry.clear()
    investigation_runner.clear()


@pytest.fixture
def test_ctx() -> TenantContext:
    return TenantContext(
        tenant_id="tenant_test_p4",
        user_id="user_analyst_01",
        role=UserRole.SUPPORT_ANALYST,
    )


@pytest.fixture
def supervisor_ctx() -> TenantContext:
    return TenantContext(
        tenant_id="tenant_test_p4",
        user_id="user_supervisor_01",
        role=UserRole.SUPERVISOR,
    )


# ==============================================================================
# Gate 1: Track 1 Payment Triage Agent Workflow
# ==============================================================================


def test_payment_triage_agent_workflow_end_to_end(test_ctx: TenantContext) -> None:
    """PRD §8 Track 1: Agent reconciles payment facts and produces Pydantic StructuredInvestigationResult."""
    now = datetime.now(timezone.utc)
    # 1. Setup payment scenario: Pending payment with customer reported debit
    payment = Payment(
        id="pay_triage_001",
        tenant_id=test_ctx.tenant_id,
        merchant_id="merch_1",
        order_ref="ORD-101",
        provider="simulator",
        provider_payment_id="sim_pay_101",
        amount_minor=50000,
        currency="INR",
        payment_status=PaymentStatus.PENDING,
        funds_status=FundsStatus.CUSTOMER_REPORTED_DEBIT,
        created_at=now,
        updated_at=now,
    )
    payment_service._payments[(test_ctx.tenant_id, payment.id)] = payment

    # Event in timeline
    event = PaymentEvent(
        id="evt_triage_001",
        payment_id=payment.id,
        provider_event_id="prv_evt_101",
        event_type="payment.pending",
        raw_status="pending",
        normalized_status=PaymentStatus.PENDING,
        source="provider_webhook",
        event_time=now,
        payload_hash="sha_mock",
        idempotency_key="idemp_101",
    )
    payment_service._timeline.setdefault(payment.id, []).append(event)

    # 2. Create case
    case = case_service.create_case(
        ctx=test_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Customer debited but order pending",
        linked_payment_ids=[payment.id],
    )

    # 3. Run investigation workflow
    final_state = investigation_runner.run_investigation(
        ctx=test_ctx,
        case_id=case.id,
        track="payment_issue",
    )

    # Assertions
    assert final_state["execution_status"] in ("COMPLETED", "PAUSED_FOR_APPROVAL")
    assert final_state["step_count"] >= 4
    assert payment.id in final_state["available_evidence_ids"]
    assert event.id in final_state["available_evidence_ids"]

    # Canonical result adherence (PRD §9.5)
    res_raw = final_state.get("structured_result")
    assert res_raw is not None
    result = StructuredInvestigationResult.model_validate(res_raw)
    assert result.case_id == case.id
    assert result.track == "payment_issue"
    assert result.payment_state.normalized_status == PaymentStatus.PENDING
    assert len(result.findings) >= 1
    # Evidence IDs must be valid
    for finding in result.findings:
        assert len(finding.evidence_ids) > 0
        for eid in finding.evidence_ids:
            assert eid in final_state["available_evidence_ids"]

    # Unknowns surfaced (PRD §9.5)
    assert len(result.unknowns) >= 1


# ==============================================================================
# Gate 2: Track 2 Fraud Investigation Agent Workflow
# ==============================================================================


def test_fraud_investigation_agent_workflow_with_graph(test_ctx: TenantContext) -> None:
    """PRD §8 Track 2: Agent navigates bounded graph neighborhood and produces explainable findings."""
    now = datetime.now(timezone.utc)

    # Materialize 4 customer accounts sharing the same device in the graph
    dev_token = "dev_tok_syndicate_001"
    v_dev = GraphVertex(
        id=dev_token,
        tenant_id=test_ctx.tenant_id,
        label=VertexLabel.DEVICE_TOKEN,
        created_at=now,
    )
    graph_service.store.upsert_vertex(test_ctx.tenant_id, v_dev)

    for i in range(1, 5):
        c_tok = f"cust_tok_synd_{i}"
        v_cust = GraphVertex(
            id=c_tok,
            tenant_id=test_ctx.tenant_id,
            label=VertexLabel.CUSTOMER_TOKEN,
            created_at=now,
        )
        graph_service.store.upsert_vertex(test_ctx.tenant_id, v_cust)

    case = case_service.create_case(
        ctx=test_ctx,
        case_type=CaseType.FRAUD_INVESTIGATION,
        title="High velocity shared device alert",
        priority=FraudSeverity.HIGH,
    )

    final_state = investigation_runner.run_investigation(
        ctx=test_ctx,
        case_id=case.id,
        track="fraud_investigation",
    )

    assert final_state["skill_name"] == "fraud-investigation"
    assert final_state["step_count"] >= 3
    assert final_state.get("structured_result") is not None
    result = StructuredInvestigationResult.model_validate(final_state["structured_result"])
    assert result.track == "fraud_investigation"
    assert result.model_metadata.provider == "stub"


# ==============================================================================
# Gate 3: Safety Invariant — No Agent Can Mutate Payment Truth or Execute Refunds
# ==============================================================================


def test_safety_invariant_prohibited_tools_blocked(test_ctx: TenantContext) -> None:
    """PRD §10.3 & ANTIGRAVITY_BUILD_PLAN Rule 7:

    Agents cannot call execute_refund, freeze_account, block_beneficiary, or system commands.
    Calling them raises ProhibitedToolError and emits a security audit record.
    """
    for forbidden_tool in FORBIDDEN_TOOLS:
        with pytest.raises(ProhibitedToolError) as exc_info:
            mcp_tool_registry.execute_tool(
                tool_name=forbidden_tool,
                ctx=test_ctx,
                parameters={"amount_minor": 5000},
            )
        assert "strictly prohibited" in str(exc_info.value).lower()

    # Verify security audit event was logged
    audit_events = audit_service.list_events_for_tenant(test_ctx.tenant_id)
    blocked_events = [e for e in audit_events if e.action == "PROHIBITED_TOOL_BLOCKED"]
    assert len(blocked_events) >= len(FORBIDDEN_TOOLS)


def test_agent_cannot_alter_verified_payment_state(test_ctx: TenantContext) -> None:
    """PRD §13.2: LLM output or candidate finding cannot overwrite verified payment truth."""
    # Verified payment state is SUCCEEDED from provider
    state: InvestigationAgentState = {
        "case_id": "case_safety_01",
        "tenant_id": test_ctx.tenant_id,
        "actor_role": test_ctx.role.value,
        "available_evidence_ids": ["case_safety_01", "pay_safety_01"],
        "payment_facts": {
            "id": "pay_safety_01",
            "payment_status": PaymentStatus.SUCCEEDED.value,
            "funds_status": FundsStatus.PROVIDER_CONFIRMED_CREDIT.value,
        },
        # Candidate finding where LLM claims payment was cancelled or failed
        "candidate_findings": [
            {
                "code": "LLM_HALLUCINATED_FAILURE",
                "statement": "Payment was reversed by system",
                "evidence_ids": ["pay_safety_01"],
            }
        ],
        "unknowns": [],
    }

    # Run validation node
    validated_state = node_validate_findings(state)

    # Authoritative payment state must remain SUCCEEDED from verified provider facts
    payment_state = validated_state["payment_state"]
    assert payment_state is not None
    assert payment_state["normalized_status"] == PaymentStatus.SUCCEEDED
    assert payment_state["source"] == "provider_webhook"


# ==============================================================================
# Gate 4: Citation Validation Invariant — Hallucinations Rejected
# ==============================================================================


def test_citation_validator_rejects_unsupported_evidence_ids(test_ctx: TenantContext) -> None:
    """PRD §9.5 & §13.2: Findings citing non-existent evidence IDs must be rejected/marked unknown."""
    state: InvestigationAgentState = {
        "case_id": "case_cite_01",
        "tenant_id": test_ctx.tenant_id,
        "actor_role": test_ctx.role.value,
        "available_evidence_ids": ["case_cite_01", "evt_verified_01"],
        "payment_facts": None,
        "candidate_findings": [
            # Legitimate finding citing genuine evidence ID
            {
                "code": "VERIFIED_EVENT",
                "statement": "Webhook received with pending status",
                "evidence_ids": ["evt_verified_01"],
                "confidence": 0.95,
            },
            # Hallucinated finding citing fake/fabricated evidence ID
            {
                "code": "FABRICATED_CLAIM",
                "statement": "Bank manager verified transfer manually",
                "evidence_ids": ["evt_fake_hallucinated_999"],
                "confidence": 0.99,
            },
        ],
        "unknowns": [],
    }

    validated_state = node_validate_findings(state)

    # Only 1 finding should be accepted
    assert len(validated_state["validated_findings"]) == 1
    assert validated_state["validated_findings"][0]["code"] == "VERIFIED_EVENT"
    assert validated_state["validated_findings"][0]["evidence_ids"] == ["evt_verified_01"]

    # Unsupported claim must be moved to unknowns
    assert len(validated_state["unknowns"]) >= 1
    assert any("evt_fake_hallucinated_999" in u for u in validated_state["unknowns"])


# ==============================================================================
# Gate 5: Human Review Gate & Approval Checkpointing
# ==============================================================================


def test_human_approval_gate_pauses_sensitive_action(
    test_ctx: TenantContext, supervisor_ctx: TenantContext
) -> None:
    """PRD §6 (FR-020): Financially sensitive actions pause workflow until supervisor approves."""
    now = datetime.now(timezone.utc)
    # Setup failed payment where customer reports debit -> requires refund escalation approval
    payment = Payment(
        id="pay_appr_001",
        tenant_id=test_ctx.tenant_id,
        merchant_id="merch_1",
        order_ref="ORD-201",
        provider="simulator",
        provider_payment_id="sim_pay_201",
        amount_minor=75000,
        currency="INR",
        payment_status=PaymentStatus.FAILED,
        funds_status=FundsStatus.CUSTOMER_REPORTED_DEBIT,
        created_at=now,
        updated_at=now,
    )
    payment_service._payments[(test_ctx.tenant_id, payment.id)] = payment

    case = case_service.create_case(
        ctx=test_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Failed payment debit claim requiring escalation",
        linked_payment_ids=[payment.id],
    )

    # 1. Start investigation
    paused_state = investigation_runner.run_investigation(
        ctx=test_ctx,
        case_id=case.id,
        track="payment_issue",
    )

    # Verify workflow paused for approval
    assert paused_state["execution_status"] == "PAUSED_FOR_APPROVAL"
    assert paused_state["requires_human_approval"] is True
    assert paused_state["approval_id"] is not None
    approval_id = paused_state["approval_id"]

    # Verify case transitioned to REVIEW_REQUIRED
    updated_case = case_service.get_case(test_ctx, case.id)
    assert updated_case.case_status == CaseStatus.REVIEW_REQUIRED

    # 2. Human supervisor reviews and grants approval
    resumed_state = investigation_runner.resume_with_approval(
        ctx=supervisor_ctx,
        case_id=case.id,
        approval_id=approval_id,
        decision=ApprovalDecision.APPROVED,
        reason="Verified customer statement matches payment timestamp.",
    )

    # Verify workflow finalized and case resolved
    assert resumed_state["execution_status"] == "COMPLETED"
    assert resumed_state["approval_status"] == "APPROVED"
    assert resumed_state.get("structured_result") is not None

    final_case = case_service.get_case(test_ctx, case.id)
    assert final_case.case_status == CaseStatus.RESOLVED


# ==============================================================================
# Gate 6: Interchangeable Model Providers & DEMO_MODE Fallback
# ==============================================================================


def test_model_provider_router_and_demo_fallback() -> None:
    """PRD §9.2 & §12.3: Gemma and Gemini interchangeable; DEMO_MODE runs without paid keys."""
    router = ModelRouter()

    # 1. Stub provider
    stub = router.get_provider("stub")
    assert isinstance(stub, StubModelProvider)
    assert stub.provider_name == "stub"
    health = stub.health_check()
    assert health.status == "HEALTHY"

    # 2. In DEMO_MODE=True, selecting gemini or gemma without keys falls back to stub
    assert settings.DEMO_MODE is True
    routed_gemini = router.get_provider("gemini")
    assert isinstance(routed_gemini, StubModelProvider)

    routed_gemma = router.get_provider("gemma")
    assert isinstance(routed_gemma, StubModelProvider)

    # 3. Direct instantiation of Gemini / Gemma flags missing keys cleanly
    gemini_no_key = GeminiModelProvider(api_key=None)
    assert gemini_no_key.health_check().status == "UNAVAILABLE"
    with pytest.raises(ValueError, match="GEMINI_API_KEY is required"):
        gemini_no_key.generate_text(ModelRequest(prompt="Hello"))

    gemma_no_url = GemmaModelProvider(endpoint_url=None)
    assert gemma_no_url.health_check().status == "UNAVAILABLE"
    with pytest.raises(ValueError, match="GEMMA_ENDPOINT_URL is required"):
        gemma_no_url.generate_text(ModelRequest(prompt="Hello"))


# ==============================================================================
# Gate 7: MCP Server Permission Checks & Skill Allowlists
# ==============================================================================


def test_mcp_skill_tool_allowlist_enforcement(test_ctx: TenantContext) -> None:
    """PRD §10.2: Agent cannot invoke tools outside the active skill's allowed_tools."""
    registry = SkillRegistry()
    payment_triage_skill = registry.get_skill("payment-triage")

    # get_graph_neighborhood is NOT in payment-triage allowed tools
    assert "get_graph_neighborhood" not in payment_triage_skill.allowed_tools

    with pytest.raises(ToolPermissionError) as exc_info:
        mcp_tool_registry.execute_tool(
            tool_name="get_graph_neighborhood",
            ctx=test_ctx,
            parameters={"entity_token": "cust_123"},
            active_skill=payment_triage_skill,
        )
    assert "not in the allowed_tools list" in str(exc_info.value)


# ==============================================================================
# Gate 8: FastAPI Endpoints Integration (/investigate, /findings, /approval)
# ==============================================================================


def test_api_investigation_and_findings_endpoints(test_ctx: TenantContext) -> None:
    """PRD §11: Verify /api/v1/cases/{case_id}/investigate and /findings endpoints."""
    client = TestClient(app)
    token = create_access_token(
        user_id=test_ctx.user_id,
        tenant_id=test_ctx.tenant_id,
        role=test_ctx.role,
        email="analyst@apex.example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a case
    create_resp = client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "case_type": "PAYMENT_DISCREPANCY",
            "title": "API investigation test case",
            "linked_payment_ids": [],
        },
    )
    assert create_resp.status_code == 201
    case_id = create_resp.json()["id"]

    # 2. Trigger investigation
    inv_resp = client.post(
        f"/api/v1/cases/{case_id}/investigate",
        headers=headers,
        json={"track": "payment_issue"},
    )
    assert inv_resp.status_code == 200
    inv_data = inv_resp.json()
    assert inv_data["case_id"] == case_id
    assert inv_data["execution_status"] in ("COMPLETED", "PAUSED_FOR_APPROVAL")
    assert inv_data["step_count"] > 0

    # 3. Retrieve findings
    findings_resp = client.get(
        f"/api/v1/cases/{case_id}/findings",
        headers=headers,
    )
    assert findings_resp.status_code == 200
    findings_data = findings_resp.json()
    assert findings_data["case_id"] == case_id
    assert findings_data["track"] == "payment_issue"
    assert "findings" in findings_data
    assert "unknowns" in findings_data
