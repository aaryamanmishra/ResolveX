"""Node implementations for LangGraph Investigation Workflows in ResolveX AI.

PRD §9.4 & §9.5: Step-by-step bounded investigation pipeline:
1. node_fetch_context: Pulls canonical facts & graph neighborhood via MCP tools.
2. node_synthesize_findings: Model reasoning using trusted skill instructions.
3. node_validate_findings: Strict Pydantic & evidence citation verification.
4. node_evaluate_policy: Deterministic policy engine for action routing.
5. node_pause_for_human_approval: Human review gate for financial/sensitive actions.
6. node_finalize_and_audit: Telemetry recording and tamper-evident audit trail.
"""

from datetime import datetime, timezone
from typing import Any

from backend.app.agent_skills.registry import SkillRegistry
from backend.app.agents.state import InvestigationAgentState
from backend.app.domain.enums import CaseStatus, PaymentStatus, UserRole
from backend.app.domain.findings import (
    InvestigationFinding,
    ModelMetadata,
    PaymentStateSummary,
    RecommendedNextStep,
    StructuredInvestigationResult,
)
from backend.app.domain.graph import GraphNeighborhood
from backend.app.domain.payment import Payment, PaymentEvent, Refund
from backend.app.mcp.tools import mcp_tool_registry
from backend.app.policies.fraud_rules import fraud_rule_engine
from backend.app.policies.payment_rules import payment_policy_engine
from backend.app.providers.model_provider import ModelRequest, get_model_provider
from backend.app.security.context import TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service

# Load trusted runtime skill registry
skill_registry = SkillRegistry()


def _get_context(state: InvestigationAgentState) -> TenantContext:
    """Helper to reconstruct TenantContext from state."""
    role_str = state.get("actor_role", "SUPPORT_ANALYST")
    try:
        role = UserRole(role_str)
    except ValueError:
        role = UserRole.SUPPORT_ANALYST

    return TenantContext(
        tenant_id=state["tenant_id"],
        user_id=state.get("user_id", "agent_runner"),
        role=role,
    )


def node_fetch_context(state: InvestigationAgentState) -> InvestigationAgentState:
    """Fetch canonical payment facts, event history, or graph neighborhood via MCP tools."""
    ctx = _get_context(state)
    case_id = state["case_id"]
    track = state.get("track", "payment_issue")

    # Select trusted skill
    skill_name = "payment-triage" if track == "payment_issue" else "fraud-investigation"
    active_skill = skill_registry.get_skill(skill_name)
    state["skill_name"] = skill_name

    available_evidence: set[str] = {case_id}
    payment_facts: dict[str, Any] | None = None
    payment_timeline: list[dict[str, Any]] = []
    refund_record: dict[str, Any] | None = None
    graph_context: dict[str, Any] | None = None

    # Load case directly from case service to obtain linked payments
    case = case_service.get_case(ctx, case_id)
    linked_payment_ids = case.linked_payment_ids
    available_evidence.add(case.id)

    # If get_case_history is allowed for the active skill, fetch audit history
    if "get_case_history" in active_skill.allowed_tools:
        case_res = mcp_tool_registry.execute_tool(
            "get_case_history", ctx, {"case_id": case_id}, active_skill
        )
        if case_res.success and case_res.data:
            available_evidence.update(case_res.evidence_ids)

    # Track 1: Payment Issue Triage
    if track == "payment_issue":
        for pid in linked_payment_ids:
            # Fetch canonical payment record
            p_res = mcp_tool_registry.execute_tool(
                "get_payment", ctx, {"payment_id": pid}, active_skill
            )
            if p_res.success and p_res.data:
                payment_facts = p_res.data
                available_evidence.update(p_res.evidence_ids)

            # Fetch payment timeline events
            e_res = mcp_tool_registry.execute_tool(
                "get_payment_events", ctx, {"payment_id": pid}, active_skill
            )
            if e_res.success and e_res.data:
                payment_timeline = e_res.data
                available_evidence.update(e_res.evidence_ids)

        # Retrieve relevant operational policy
        pol_res = mcp_tool_registry.execute_tool(
            "retrieve_policy", ctx, {"query": "payment_triage"}, active_skill
        )
        if pol_res.success:
            state["retrieved_policy"] = pol_res.data.get("policy_text")
            available_evidence.update(pol_res.evidence_ids)

    # Track 2: Fraud Investigation
    else:
        # Default customer token for neighborhood query
        entity_token = "cust_tok_synth_001"
        if linked_payment_ids:
            p_res = mcp_tool_registry.execute_tool(
                "get_payment", ctx, {"payment_id": linked_payment_ids[0]}, active_skill
            )
            if p_res.success and p_res.data:
                entity_token = p_res.data.get("customer_id", entity_token)
                payment_facts = p_res.data
                available_evidence.update(p_res.evidence_ids)

        # Fetch bounded graph neighborhood
        g_res = mcp_tool_registry.execute_tool(
            "get_graph_neighborhood",
            ctx,
            {"entity_token": entity_token, "depth": 2},
            active_skill,
        )
        if g_res.success and g_res.data:
            graph_context = g_res.data
            available_evidence.update(g_res.evidence_ids)

        # Retrieve relevant fraud policy
        pol_res = mcp_tool_registry.execute_tool(
            "retrieve_policy", ctx, {"query": "fraud_investigation"}, active_skill
        )
        if pol_res.success:
            state["retrieved_policy"] = pol_res.data.get("policy_text")
            available_evidence.update(pol_res.evidence_ids)

    state["payment_facts"] = payment_facts
    state["payment_timeline"] = payment_timeline
    state["refund_record"] = refund_record
    state["graph_context"] = graph_context
    state["available_evidence_ids"] = sorted(list(available_evidence))
    state["step_count"] = state.get("step_count", 0) + 1
    return state


def node_synthesize_findings(state: InvestigationAgentState) -> InvestigationAgentState:
    """Invoke the active model provider with trusted skill instructions to synthesize candidate findings."""
    model_provider = get_model_provider()
    track = state.get("track", "payment_issue")
    active_skill = skill_registry.get_skill(state["skill_name"])

    prompt = (
        f"Case ID: {state['case_id']}\n"
        f"Track: {track}\n"
        f"Policy: {state.get('retrieved_policy', '')}\n"
        f"Available Evidence IDs: {', '.join(state.get('available_evidence_ids', []))}\n"
        f"Payment Facts: {state.get('payment_facts')}\n"
        f"Graph Context: {state.get('graph_context')}\n\n"
        f"Instructions:\n{active_skill.instructions}\n"
    )

    request = ModelRequest(
        prompt=prompt,
        system_instruction=(
            "You are ResolveX AI, an agentic financial operations investigator. "
            "You MUST ground every finding in cited evidence IDs from Available Evidence IDs. "
            "Never fabricate IDs, timestamps, or bank confirmations. "
            "Never suggest financial mutations or automatic funds blocking."
        ),
        temperature=0.0,
    )

    structured_res = model_provider.generate_structured(request, StructuredInvestigationResult)
    parsed = structured_res.parsed

    state["raw_model_response"] = structured_res.raw_json
    state["synthesis_summary"] = parsed.summary
    state["candidate_findings"] = [f.model_dump(mode="json") for f in parsed.findings]
    state["step_count"] = state.get("step_count", 0) + 1
    return state


def node_validate_findings(state: InvestigationAgentState) -> InvestigationAgentState:
    """Enforce PRD §9.5: Strict Pydantic validation & citation verification.

    Every finding MUST cite genuine evidence IDs present in available_evidence_ids.
    Unsupported or hallucinated claims are rejected and placed in unknowns.
    Provider-confirmed payment status can NEVER be altered by the LLM.
    """
    valid_evidence_set = set(state.get("available_evidence_ids", []))
    candidate_findings = state.get("candidate_findings", [])
    validated: list[dict[str, Any]] = []
    unknowns: list[str] = list(state.get("unknowns", []))

    for item in candidate_findings:
        raw_ids = item.get("evidence_ids", [])
        # Filter to only IDs that exist in the canonical context
        verified_ids = [eid for eid in raw_ids if eid in valid_evidence_set]

        if not verified_ids:
            # Finding has no valid evidence backing -> mark as unknown / reject
            unknown_statement = (
                f"Unverified claim: {item.get('statement')} (missing evidence: {raw_ids})"
            )
            unknowns.append(unknown_statement)
            continue

        validated_finding = InvestigationFinding(
            code=item.get("code", "OBSERVED_FINDING"),
            statement=item.get("statement", "Grounded finding based on verified records."),
            evidence_ids=verified_ids,
            confidence=min(float(item.get("confidence", 0.9)), 1.0),
            uncertainty=item.get("uncertainty"),
        )
        validated.append(validated_finding.model_dump(mode="json"))

    # Preserve authoritative payment status from authenticated provider facts
    payment_facts = state.get("payment_facts")
    if payment_facts:
        status_str = payment_facts.get("payment_status", PaymentStatus.PENDING)
        try:
            norm_status = PaymentStatus(status_str)
        except ValueError:
            norm_status = PaymentStatus.PENDING

        payment_state = PaymentStateSummary(
            normalized_status=norm_status,
            source="provider_webhook",
            as_of=datetime.now(timezone.utc),
        )
    else:
        payment_state = PaymentStateSummary(
            normalized_status=PaymentStatus.PENDING,
            source="investigation_pipeline",
            as_of=datetime.now(timezone.utc),
        )

    state["validated_findings"] = validated
    state["unknowns"] = unknowns
    state["payment_state"] = payment_state.model_dump(mode="json")
    state["step_count"] = state.get("step_count", 0) + 1
    return state


def node_evaluate_policy(state: InvestigationAgentState) -> InvestigationAgentState:
    """Apply deterministic policy rules to govern proposed action and human review gating.

    PRD §6 (FR-020): Any financial action, refund escalation, or high-risk fraud finding
    MUST require explicit human approval (requires_human_approval = True).
    """
    ctx = _get_context(state)
    case_id = state["case_id"]
    track = state.get("track", "payment_issue")

    if track == "payment_issue":
        payment_facts = state.get("payment_facts") or {}
        payment_obj = (
            Payment.model_validate(payment_facts)
            if payment_facts
            else Payment(
                id=f"pay_{case_id}",
                tenant_id=state["tenant_id"],
                merchant_id="merch_default",
                order_ref=f"ord_{case_id}",
                provider="simulator",
                provider_payment_id=f"prov_{case_id}",
                amount_minor=1000,
                currency="INR",
            )
        )
        timeline_events = [
            PaymentEvent.model_validate(e) for e in state.get("payment_timeline", [])
        ]
        refund_obj = (
            Refund.model_validate(state["refund_record"]) if state.get("refund_record") else None
        )

        eval_result = payment_policy_engine.evaluate_payment(
            case_id=case_id,
            payment=payment_obj,
            timeline=timeline_events,
            refund=refund_obj,
        )

        state["proposed_action"] = eval_result.recommended_step.model_dump(mode="json")
        state["requires_human_approval"] = eval_result.requires_human_approval
        state["unknowns"].extend(eval_result.unknowns)

    else:
        # Fraud track deterministic evaluation
        graph_data = state.get("graph_context") or {}
        neighborhood = (
            GraphNeighborhood.model_validate(graph_data)
            if graph_data
            else GraphNeighborhood(center_vertex_id="cust_demo", depth=1)
        )

        fraud_result = fraud_rule_engine.evaluate_neighborhood(
            case_id=case_id, neighborhood=neighborhood
        )

        recommended_step = RecommendedNextStep(
            action="REQUEST_SUPERVISOR_REVIEW" if fraud_result.is_alert else "CLOSE_AS_BENIGN",
            requires_human_approval=fraud_result.requires_human_review,
            external_side_effect=False,
            action_payload={"severity": fraud_result.severity.value},
        )

        state["proposed_action"] = recommended_step.model_dump(mode="json")
        state["requires_human_approval"] = fraud_result.requires_human_review

    # If action requires approval, create an Approval draft in the case service
    if state["requires_human_approval"]:
        approval = case_service.create_approval_draft(
            ctx=ctx,
            case_id=case_id,
            action_draft=state["proposed_action"] or {},
        )
        state["approval_id"] = approval.id
        state["approval_status"] = "PENDING"
    else:
        state["approval_status"] = "NOT_REQUIRED"

    state["step_count"] = state.get("step_count", 0) + 1
    return state


def node_pause_for_human_approval(state: InvestigationAgentState) -> InvestigationAgentState:
    """Human Review Gate: Pauses execution until an authorized human signs off on sensitive action."""
    ctx = _get_context(state)
    case_id = state["case_id"]

    # Transition case to REVIEW_REQUIRED
    case_service.update_case_status(
        ctx=ctx,
        case_id=case_id,
        new_status=CaseStatus.REVIEW_REQUIRED,
        reason="Agent investigation generated recommendation requiring human approval.",
    )

    state["execution_status"] = "PAUSED_FOR_APPROVAL"
    state["step_count"] = state.get("step_count", 0) + 1
    return state


def node_finalize_and_audit(state: InvestigationAgentState) -> InvestigationAgentState:
    """Assemble final canonical StructuredInvestigationResult, log AgentRun and immutable audit event."""
    ctx = _get_context(state)
    case_id = state["case_id"]
    track = state.get("track", "payment_issue")

    # Formulate canonical output conforming to PRD §9.5
    final_result = StructuredInvestigationResult(
        case_id=case_id,
        track=track,
        summary=state.get(
            "synthesis_summary",
            "Investigation concluded with verified findings and deterministic policy.",
        ),
        payment_state=PaymentStateSummary.model_validate(state["payment_state"]),
        findings=[
            InvestigationFinding.model_validate(f) for f in state.get("validated_findings", [])
        ],
        unknowns=state.get("unknowns", []),
        recommended_next_step=RecommendedNextStep.model_validate(state["proposed_action"]),
        model_metadata=ModelMetadata(
            provider=get_model_provider().provider_name,
            model_id="configured-model",
            prompt_version=f"{state.get('skill_name', 'triage')}-v1",
            execution_time_ms=state.get("latency_ms", 50),
        ),
    )

    state["structured_result"] = final_result.model_dump(mode="json")
    state["execution_status"] = "COMPLETED"

    # Emit audit event for investigation completion
    audit_service.record(
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action="AGENT_INVESTIGATION_COMPLETED",
        resource_type="Case",
        resource_id=case_id,
        details={
            "track": track,
            "skill": state.get("skill_name"),
            "findings_count": len(state.get("validated_findings", [])),
            "unknowns_count": len(state.get("unknowns", [])),
            "requires_human_approval": state.get("requires_human_approval", False),
            "approval_status": state.get("approval_status"),
        },
    )

    state["step_count"] = state.get("step_count", 0) + 1
    return state
