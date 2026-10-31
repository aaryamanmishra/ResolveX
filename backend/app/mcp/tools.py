"""Model Context Protocol (MCP) Tool Implementation for ResolveX AI.

PRD §10.3: Narrow, typed, server-side validated tools for AI agent workflows.
Every tool call enforces:
1. Tenant boundary validation (no cross-tenant leakage).
2. Role-based access control (RBAC).
3. Skill allowlist validation (tool must be explicitly allowed by the active skill).
4. Strict prohibition of financial mutations (NO execute_refund, freeze_account, etc.).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.app.agent_skills.registry import RuntimeSkillManifest
from backend.app.domain.payment import Payment
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service
from backend.app.services.graph_service import graph_service
from backend.app.services.payment_service import payment_service


class MCPToolError(Exception):
    """Base exception for MCP tool errors."""

    pass


class ProhibitedToolError(MCPToolError):
    """Raised when an agent attempts to invoke a forbidden operational tool."""

    pass


class ToolPermissionError(MCPToolError):
    """Raised when an agent skill lacks permission to execute a tool."""

    pass


@dataclass(frozen=True)
class MCPToolResult:
    """Standardized response from an MCP tool invocation."""

    tool_name: str
    success: bool
    data: Any
    evidence_ids: list[str]
    error: str | None = None
    timestamp: datetime = datetime.now(timezone.utc)


# Prohibited tools that an AI agent is strictly forbidden from invoking in MVP
FORBIDDEN_TOOLS: frozenset[str] = frozenset(
    [
        "execute_refund",
        "freeze_account",
        "block_beneficiary",
        "reverse_payment",
        "execute_sql",
        "run_shell",
        "modify_payment_state",
    ]
)


class MCPToolRegistry:
    """Registry and executor for typed MCP tools with mandatory safety controls."""

    def __init__(self) -> None:
        self._evidence_store: dict[tuple[str, str], dict[str, Any]] = {}

    def register_mock_evidence(
        self, tenant_id: str, evidence_id: str, evidence_data: dict[str, Any]
    ) -> None:
        """Register evidence metadata for testing/triage."""
        self._evidence_store[(tenant_id, evidence_id)] = evidence_data

    def clear(self) -> None:
        self._evidence_store.clear()

    def execute_tool(
        self,
        tool_name: str,
        ctx: TenantContext,
        parameters: dict[str, Any],
        active_skill: RuntimeSkillManifest | None = None,
    ) -> MCPToolResult:
        """Execute an MCP tool subject to strict permission and safety boundaries."""
        # 1. Prohibited tool check
        if tool_name in FORBIDDEN_TOOLS:
            audit_service.record(
                tenant_id=ctx.tenant_id,
                actor_id=ctx.user_id,
                action="PROHIBITED_TOOL_BLOCKED",
                resource_type="MCPTool",
                resource_id=tool_name,
                details={
                    "parameters": parameters,
                    "reason": "Agent is strictly forbidden from financial mutations or system commands.",
                },
            )
            raise ProhibitedToolError(
                f"Security Violation: Tool '{tool_name}' is strictly prohibited for AI agents. "
                f"Financial and system mutations require explicit human review."
            )

        # 2. Skill allowlist validation
        if active_skill and tool_name not in active_skill.allowed_tools:
            raise ToolPermissionError(
                f"Permission Denied: Tool '{tool_name}' is not in the allowed_tools list for skill '{active_skill.name}'. "
                f"Allowed tools: {active_skill.allowed_tools}"
            )

        # 3. Dispatch to typed handler
        handler_name = f"_tool_{tool_name}"
        handler = getattr(self, handler_name, None)
        if not handler:
            raise MCPToolError(f"Unknown MCP tool: '{tool_name}'")

        try:
            res: MCPToolResult = handler(ctx=ctx, **parameters)
            return res
        except SecurityError as sec_err:
            raise ToolPermissionError(str(sec_err)) from sec_err
        except Exception as exc:
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                evidence_ids=[],
                error=str(exc),
            )

    # --------------------------------------------------------------------------
    # PRD §10.3 Typed Tool Implementations
    # --------------------------------------------------------------------------

    def _tool_get_payment(self, ctx: TenantContext, payment_id: str) -> MCPToolResult:
        """Fetch canonical payment record."""
        try:
            payment = payment_service.get_payment(ctx, payment_id)
            return MCPToolResult(
                tool_name="get_payment",
                success=True,
                data=payment.model_dump(mode="json"),
                evidence_ids=[payment.id],
            )
        except KeyError:
            return MCPToolResult(
                tool_name="get_payment",
                success=False,
                data=None,
                evidence_ids=[],
                error=f"Payment '{payment_id}' not found.",
            )

    def _tool_get_payment_events(
        self,
        ctx: TenantContext,
        payment_id: str,
        since: str | None = None,
        limit: int = 50,
    ) -> MCPToolResult:
        """Fetch timeline of provider/system events for a payment."""
        events = payment_service.get_timeline(ctx, payment_id)
        evidence_ids = [e.id for e in events]
        return MCPToolResult(
            tool_name="get_payment_events",
            success=True,
            data=[e.model_dump(mode="json") for e in events[:limit]],
            evidence_ids=evidence_ids,
        )

    def _tool_get_provider_payment_status(
        self, ctx: TenantContext, payment_id: str
    ) -> MCPToolResult:
        """Fetch provider-confirmed payment status snapshot."""
        try:
            payment = payment_service.get_payment(ctx, payment_id)
            return MCPToolResult(
                tool_name="get_provider_payment_status",
                success=True,
                data={
                    "payment_id": payment.id,
                    "normalized_status": payment.payment_status.value,
                    "funds_status": payment.funds_status.value,
                    "provider": payment.provider,
                    "provider_payment_id": payment.provider_payment_id,
                    "updated_at": payment.updated_at.isoformat(),
                },
                evidence_ids=[payment.id],
            )
        except KeyError:
            return MCPToolResult(
                tool_name="get_provider_payment_status",
                success=False,
                data=None,
                evidence_ids=[],
                error=f"Payment '{payment_id}' not found.",
            )

    def _tool_get_refund_status(self, ctx: TenantContext, refund_id: str) -> MCPToolResult:
        """Fetch refund status and timeline."""
        try:
            refund = payment_service.get_refund(ctx, refund_id)
            return MCPToolResult(
                tool_name="get_refund_status",
                success=True,
                data=refund.model_dump(mode="json"),
                evidence_ids=[refund.id],
            )
        except KeyError:
            return MCPToolResult(
                tool_name="get_refund_status",
                success=False,
                data=None,
                evidence_ids=[],
                error=f"Refund '{refund_id}' not found.",
            )

    def _tool_search_transactions(
        self, ctx: TenantContext, criteria: dict[str, Any], limit: int = 50
    ) -> MCPToolResult:
        """Search payments by criteria (status, customer_id, order_id)."""
        payments = payment_service.list_payments(ctx, limit=limit)
        filtered: list[Payment] = []
        for p in payments:
            match = True
            for k, v in criteria.items():
                if getattr(p, k, None) != v:
                    match = False
                    break
            if match:
                filtered.append(p)

        return MCPToolResult(
            tool_name="search_transactions",
            success=True,
            data=[p.model_dump(mode="json") for p in filtered[:limit]],
            evidence_ids=[p.id for p in filtered[:limit]],
        )

    def _tool_get_graph_neighborhood(
        self,
        ctx: TenantContext,
        entity_token: str,
        entity_type: str = "CustomerToken",
        depth: int = 2,
        limit: int = 50,
    ) -> MCPToolResult:
        """Retrieve tokenized graph neighborhood for an entity."""
        neighborhood = graph_service.query_neighborhood(
            ctx=ctx,
            entity_token=entity_token,
            depth=min(depth, 3),
            limit=min(limit, 100),
        )
        evidence_ids = [v.id for v in neighborhood.vertices] + [e.id for e in neighborhood.edges]
        return MCPToolResult(
            tool_name="get_graph_neighborhood",
            success=True,
            data=neighborhood.model_dump(mode="json"),
            evidence_ids=evidence_ids,
        )

    def _tool_get_case_history(self, ctx: TenantContext, case_id: str) -> MCPToolResult:
        """Retrieve case details, linked payments, and audit history."""
        case = case_service.get_case(ctx, case_id)
        audit_events = audit_service.get_history(ctx, resource_id=case_id)
        evidence_ids = [case.id] + [a.id for a in audit_events] + case.linked_payment_ids
        return MCPToolResult(
            tool_name="get_case_history",
            success=True,
            data={
                "case": case.model_dump(mode="json"),
                "audit_events": [a.model_dump(mode="json") for a in audit_events],
            },
            evidence_ids=evidence_ids,
        )

    def _tool_retrieve_policy(
        self, ctx: TenantContext, query: str, policy_version: str = "v1"
    ) -> MCPToolResult:
        """Retrieve deterministic policy guidelines and escalation rules."""
        # Built-in policy corpus for payments and fraud
        policies = {
            "payment_triage": (
                "Policy REF-POL-01: (1) If payment is SUCCEEDED, resolve case. "
                "(2) If payment is PENDING and customer reports debit, verify provider final status or wait for SLA (T+24h). "
                "(3) If payment is FAILED and debit reported, request bank statement before proposing refund. "
                "(4) Any proposed refund MUST be drafted as an approval request for human supervisor sign-off."
            ),
            "fraud_investigation": (
                "Policy FRD-POL-02: (1) Shared device count > 3 accounts requires High severity and human review. "
                "(2) Benign household (<= 2 accounts) must not trigger automatic fraud alerts. "
                "(3) Smurfing pattern (>= 3 payment instruments used on same customer) triggers Medium severity. "
                "(4) AI agents are strictly forbidden from auto-blocking accounts or freezing funds."
            ),
            "refund_resolution": (
                "Policy REF-POL-03: (1) Refunds pending > 5 business days violate SLA. "
                "(2) Escalate delayed refunds to banking operations. "
                "(3) Supervisor approval is required for all manual refund overrides."
            ),
        }

        # Select relevant policy
        matched_text = policies.get("payment_triage")
        for key, val in policies.items():
            if key in query.lower() or query.lower() in key:
                matched_text = val
                break

        return MCPToolResult(
            tool_name="retrieve_policy",
            success=True,
            data={"policy_version": policy_version, "policy_text": matched_text},
            evidence_ids=[f"POL_{policy_version}"],
        )

    def _tool_get_evidence_metadata(self, ctx: TenantContext, evidence_id: str) -> MCPToolResult:
        """Retrieve metadata for uploaded evidence asset."""
        key = (ctx.tenant_id, evidence_id)
        if key in self._evidence_store:
            return MCPToolResult(
                tool_name="get_evidence_metadata",
                success=True,
                data=self._evidence_store[key],
                evidence_ids=[evidence_id],
            )

        # Default fallback for testing
        return MCPToolResult(
            tool_name="get_evidence_metadata",
            success=True,
            data={
                "id": evidence_id,
                "tenant_id": ctx.tenant_id,
                "file_name": f"{evidence_id}.pdf",
                "mime_type": "application/pdf",
                "verified": False,
            },
            evidence_ids=[evidence_id],
        )

    def _tool_extract_evidence_claims(
        self, ctx: TenantContext, evidence_id: str, extraction_profile: str = "standard"
    ) -> MCPToolResult:
        """Extract factual claims from an evidence item."""
        claims = [
            {
                "claim_id": f"claim_{evidence_id}_01",
                "field_name": "customer_reported_amount",
                "candidate_value": "50000",
                "confidence": 0.94,
            }
        ]
        return MCPToolResult(
            tool_name="extract_evidence_claims",
            success=True,
            data={"evidence_id": evidence_id, "claims": claims},
            evidence_ids=[evidence_id, f"claim_{evidence_id}_01"],
        )

    def _tool_create_case_draft(
        self, ctx: TenantContext, case_payload: dict[str, Any]
    ) -> MCPToolResult:
        """Draft a new case or update proposal."""
        return MCPToolResult(
            tool_name="create_case_draft",
            success=True,
            data={"status": "DRAFT_CREATED", "payload": case_payload},
            evidence_ids=[],
        )

    def _tool_request_additional_evidence(
        self, ctx: TenantContext, case_id: str, request_payload: dict[str, Any]
    ) -> MCPToolResult:
        """Request additional evidence (e.g. bank statement) from customer/analyst."""
        # Ensure case exists
        case_service.get_case(ctx, case_id)
        return MCPToolResult(
            tool_name="request_additional_evidence",
            success=True,
            data={
                "case_id": case_id,
                "status": "EVIDENCE_REQUESTED",
                "requested_items": request_payload.get("requested_items", ["bank_statement"]),
            },
            evidence_ids=[case_id],
        )

    def _tool_draft_resolution_recommendation(
        self, ctx: TenantContext, case_id: str, recommendation: dict[str, Any]
    ) -> MCPToolResult:
        """Draft a proposed resolution recommendation (requires human approval if financial)."""
        # Ensure case exists
        case = case_service.get_case(ctx, case_id)
        return MCPToolResult(
            tool_name="draft_resolution_recommendation",
            success=True,
            data={
                "case_id": case.id,
                "recommendation": recommendation,
                "requires_approval": recommendation.get("requires_approval", True),
            },
            evidence_ids=[case.id],
        )


# Global singleton instance
mcp_tool_registry = MCPToolRegistry()
