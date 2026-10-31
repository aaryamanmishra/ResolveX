"""LangGraph Investigation Workflow Definition and Runner for ResolveX AI.

PRD §9.4 & §12.1: Bounded, stateful investigation graph with checkpointing,
deterministic policy verification, and human-in-the-loop approval pause.
"""

import time
import uuid
from typing import Literal, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from backend.app.agents.nodes import (
    node_evaluate_policy,
    node_fetch_context,
    node_finalize_and_audit,
    node_pause_for_human_approval,
    node_synthesize_findings,
    node_validate_findings,
)
from backend.app.agents.state import InvestigationAgentState
from backend.app.domain.enums import ApprovalDecision, CaseStatus
from backend.app.domain.findings import StructuredInvestigationResult
from backend.app.security.context import TenantContext
from backend.app.services.case_service import case_service

MAX_INVESTIGATION_STEPS = 12


def approval_router(state: InvestigationAgentState) -> Literal["pause_for_approval", "finalize"]:
    """Conditional edge: routes to human approval gate if sensitive action proposed."""
    if state.get("requires_human_approval") and state.get("approval_status") == "PENDING":
        return "pause_for_approval"
    return "finalize"


def build_investigation_graph() -> StateGraph:
    """Build and compile the LangGraph investigation workflow."""
    workflow = StateGraph(InvestigationAgentState)

    # 1. Add nodes
    workflow.add_node("fetch_context", node_fetch_context)
    workflow.add_node("synthesize_findings", node_synthesize_findings)
    workflow.add_node("validate_findings", node_validate_findings)
    workflow.add_node("evaluate_policy", node_evaluate_policy)
    workflow.add_node("pause_for_approval", node_pause_for_human_approval)
    workflow.add_node("finalize", node_finalize_and_audit)

    # 2. Add edges
    workflow.add_edge(START, "fetch_context")
    workflow.add_edge("fetch_context", "synthesize_findings")
    workflow.add_edge("synthesize_findings", "validate_findings")
    workflow.add_edge("validate_findings", "evaluate_policy")

    # Conditional routing after deterministic policy evaluation
    workflow.add_conditional_edges(
        "evaluate_policy",
        approval_router,
        {
            "pause_for_approval": "pause_for_approval",
            "finalize": "finalize",
        },
    )

    workflow.add_edge("pause_for_approval", END)
    workflow.add_edge("finalize", END)

    return workflow


class InvestigationWorkflowRunner:
    """Manages execution and checkpointing of LangGraph investigation runs."""

    def __init__(self) -> None:
        self.checkpointer = MemorySaver()
        self.graph = build_investigation_graph().compile(checkpointer=self.checkpointer)
        # Store latest findings cache keyed by (tenant_id, case_id) -> StructuredInvestigationResult
        self._latest_findings: dict[tuple[str, str], StructuredInvestigationResult] = {}

    def run_investigation(
        self,
        ctx: TenantContext,
        case_id: str,
        track: Literal["payment_issue", "fraud_investigation"] = "payment_issue",
    ) -> InvestigationAgentState:
        """Execute investigation workflow from initiation up to completion or human pause."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        # Update case to TRIAGING
        case_service.update_case_status(
            ctx=ctx,
            case_id=case_id,
            new_status=CaseStatus.TRIAGING,
            reason="Investigation workflow started.",
        )

        initial_state: InvestigationAgentState = {
            "case_id": case_id,
            "tenant_id": ctx.tenant_id,
            "user_id": ctx.user_id,
            "actor_role": ctx.role.value,
            "track": track,
            "skill_name": "payment-triage" if track == "payment_issue" else "fraud-investigation",
            "run_id": run_id,
            "available_evidence_ids": [case_id],
            "step_count": 0,
            "max_steps": MAX_INVESTIGATION_STEPS,
            "execution_status": "RUNNING",
            "requires_human_approval": False,
            "approval_status": "NOT_REQUIRED",
            "unknowns": [],
            "latency_ms": 0,
        }

        config = RunnableConfig(configurable={"thread_id": f"{ctx.tenant_id}:{case_id}"})
        final_state: InvestigationAgentState = cast(
            InvestigationAgentState, self.graph.invoke(initial_state, config=config)
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        final_state["latency_ms"] = elapsed_ms

        # Cache structured result if available
        if final_state.get("structured_result"):
            res = StructuredInvestigationResult.model_validate(final_state["structured_result"])
            self._latest_findings[(ctx.tenant_id, case_id)] = res

        return final_state

    def resume_with_approval(
        self,
        ctx: TenantContext,
        case_id: str,
        approval_id: str,
        decision: ApprovalDecision,
        reason: str | None = None,
    ) -> InvestigationAgentState:
        """Resume paused workflow after a human reviewer records approval/rejection."""
        # Record human approval decision in case service
        case_service.decide_approval(
            ctx=ctx,
            approval_id=approval_id,
            decision=decision,
            reason=reason,
        )

        config = RunnableConfig(configurable={"thread_id": f"{ctx.tenant_id}:{case_id}"})
        snapshot = self.graph.get_state(config)

        if not snapshot or not snapshot.values:
            # Fall back to running fresh run
            return self.run_investigation(ctx, case_id)

        state: InvestigationAgentState = dict(snapshot.values)  # type: ignore[assignment]
        state["approval_status"] = decision.value
        state["approval_reason"] = reason

        if decision == ApprovalDecision.APPROVED:
            # Complete investigation
            state = node_finalize_and_audit(state)
            case_service.update_case_status(
                ctx=ctx,
                case_id=case_id,
                new_status=CaseStatus.RESOLVED,
                reason=f"Action approved by human reviewer: {reason or 'Approved'}",
            )
        else:
            state["execution_status"] = "COMPLETED"
            case_service.update_case_status(
                ctx=ctx,
                case_id=case_id,
                new_status=CaseStatus.ESCALATED,
                reason=f"Action rejected by human reviewer: {reason or 'Rejected'}",
            )

        if state.get("structured_result"):
            res = StructuredInvestigationResult.model_validate(state["structured_result"])
            self._latest_findings[(ctx.tenant_id, case_id)] = res

        return state

    def get_latest_findings(
        self, ctx: TenantContext, case_id: str
    ) -> StructuredInvestigationResult | None:
        """Retrieve cached structured findings for a case."""
        return self._latest_findings.get((ctx.tenant_id, case_id))

    def clear(self) -> None:
        """Reset state for tests."""
        self._latest_findings.clear()


# Global runner singleton
investigation_runner = InvestigationWorkflowRunner()
