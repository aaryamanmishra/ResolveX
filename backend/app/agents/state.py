"""State definition for LangGraph Agent Workflows in ResolveX AI.

PRD §9.4 & §9.5: Typed state containing canonical payment facts, graph context,
trusted skill metadata, evidence citations, deterministic policy results,
and human approval gate status.
"""

from typing import Any, Literal, TypedDict


class InvestigationAgentState(TypedDict, total=False):
    """Canonical state container passed through LangGraph workflow nodes."""

    # Execution Identity & Tenancy
    case_id: str
    tenant_id: str
    user_id: str
    track: Literal["payment_issue", "fraud_investigation"]
    actor_role: str
    skill_name: str
    run_id: str

    # Retrieved Context & Evidence
    payment_facts: dict[str, Any] | None
    payment_timeline: list[dict[str, Any]]
    refund_record: dict[str, Any] | None
    graph_context: dict[str, Any] | None
    retrieved_policy: str | None
    available_evidence_ids: list[str]

    # Synthesis & Candidate Findings
    raw_model_response: str | None
    candidate_findings: list[dict[str, Any]]
    synthesis_summary: str

    # Validated Evidence & Schema Adherence
    validated_findings: list[dict[str, Any]]
    unknowns: list[str]
    payment_state: dict[str, Any] | None

    # Deterministic Policy & Human Review Gate
    proposed_action: dict[str, Any] | None
    requires_human_approval: bool
    approval_id: str | None
    approval_status: str  # "NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED"
    approval_reason: str | None

    # Final Canonical Result
    structured_result: dict[str, Any] | None

    # Workflow Control & Telemetry
    step_count: int
    max_steps: int
    execution_status: str  # "RUNNING", "PAUSED_FOR_APPROVAL", "COMPLETED", "FAILED"
    error: str | None
    latency_ms: int
