"""Case management and triage service for ResolveX AI.

PRD §6 (FR-009 & FR-020): Manages cases, assignments, status transitions,
and ensures all state changes emit immutable audit logs under the tenant boundary.
"""

import uuid
from datetime import datetime, timezone

from backend.app.domain.case import Approval, Case
from backend.app.domain.enums import ApprovalDecision, CaseStatus, CaseType, FraudSeverity
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.audit_service import audit_service


class CaseService:
    """Manages case operations with tenant isolation and audit logging."""

    def __init__(self) -> None:
        # In-memory store keyed by (tenant_id, case_id) -> Case
        self._cases: dict[tuple[str, str], Case] = {}
        # Approvals keyed by (tenant_id, approval_id) -> Approval
        self._approvals: dict[tuple[str, str], Approval] = {}

    def create_case(
        self,
        ctx: TenantContext,
        case_type: CaseType,
        title: str,
        description: str = "",
        linked_payment_ids: list[str] | None = None,
        priority: FraudSeverity = FraudSeverity.LOW,
        correlation_id: str | None = None,
    ) -> Case:
        """Create a new case in the caller's tenant."""
        case_id = f"case_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        new_case = Case(
            id=case_id,
            tenant_id=ctx.tenant_id,
            case_type=case_type,
            title=title,
            description=description,
            linked_payment_ids=linked_payment_ids or [],
            priority=priority,
            case_status=CaseStatus.NEW,
            owner_id=ctx.user_id,
            created_at=now,
            updated_at=now,
        )

        self._cases[(ctx.tenant_id, case_id)] = new_case

        # Emit audit event
        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="CASE_CREATED",
            resource_type="Case",
            resource_id=case_id,
            details={
                "case_type": case_type.value,
                "title": title,
                "priority": priority.value,
                "linked_payment_ids": linked_payment_ids or [],
            },
            correlation_id=correlation_id,
        )

        return new_case

    def get_case(self, ctx: TenantContext, case_id: str) -> Case:
        """Retrieve case, ensuring cross-tenant isolation."""
        key = (ctx.tenant_id, case_id)
        if key not in self._cases:
            # Check if case exists in any other tenant to verify fail-closed behavior
            for (other_tenant, other_id), _ in self._cases.items():
                if other_id == case_id and other_tenant != ctx.tenant_id:
                    raise SecurityError(
                        f"Cross-tenant access forbidden: Actor tenant '{ctx.tenant_id}' cannot view case '{case_id}'"
                    )
            raise KeyError(f"Case '{case_id}' not found in tenant '{ctx.tenant_id}'")

        return self._cases[key]

    def list_cases(
        self,
        ctx: TenantContext,
        status_filter: CaseStatus | None = None,
        limit: int = 50,
    ) -> list[Case]:
        """List cases scoped to caller's tenant."""
        results = [
            c
            for (tid, _), c in self._cases.items()
            if tid == ctx.tenant_id and (status_filter is None or c.case_status == status_filter)
        ]
        return results[:limit]

    def update_case_status(
        self,
        ctx: TenantContext,
        case_id: str,
        new_status: CaseStatus,
        reason: str | None = None,
        correlation_id: str | None = None,
    ) -> Case:
        """Update case status and log audit trail."""
        case = self.get_case(ctx, case_id)
        old_status = case.case_status

        updated_case = Case(
            id=case.id,
            tenant_id=case.tenant_id,
            case_type=case.case_type,
            title=case.title,
            description=case.description,
            linked_payment_ids=case.linked_payment_ids,
            priority=case.priority,
            case_status=new_status,
            owner_id=case.owner_id,
            created_at=case.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._cases[(ctx.tenant_id, case_id)] = updated_case

        # Emit audit event
        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="CASE_STATUS_UPDATED",
            resource_type="Case",
            resource_id=case_id,
            details={
                "old_status": old_status.value,
                "new_status": new_status.value,
                "reason": reason,
            },
            correlation_id=correlation_id,
        )

        return updated_case

    def create_approval_draft(
        self,
        ctx: TenantContext,
        case_id: str,
        action_draft: dict,
        correlation_id: str | None = None,
    ) -> Approval:
        """Create a pending approval draft for human review."""
        # Ensure case exists and belongs to tenant
        self.get_case(ctx, case_id)

        approval_id = f"appr_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        approval = Approval(
            id=approval_id,
            case_id=case_id,
            tenant_id=ctx.tenant_id,
            action_draft=action_draft,
            requested_by=ctx.user_id,
            decision=ApprovalDecision.PENDING,
            reviewed_by=None,
            reason=None,
            timestamp=now,
        )
        self._approvals[(ctx.tenant_id, approval_id)] = approval

        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="APPROVAL_REQUESTED",
            resource_type="Approval",
            resource_id=approval_id,
            details={"case_id": case_id, "action_draft": action_draft},
            correlation_id=correlation_id,
        )
        return approval

    def decide_approval(
        self,
        ctx: TenantContext,
        approval_id: str,
        decision: ApprovalDecision,
        reason: str | None = None,
        correlation_id: str | None = None,
    ) -> Approval:
        """Record human reviewer decision on an approval draft."""
        key = (ctx.tenant_id, approval_id)
        if key not in self._approvals:
            raise KeyError(f"Approval '{approval_id}' not found in tenant '{ctx.tenant_id}'")

        existing = self._approvals[key]
        now = datetime.now(timezone.utc)

        updated = Approval(
            id=existing.id,
            case_id=existing.case_id,
            tenant_id=existing.tenant_id,
            action_draft=existing.action_draft,
            requested_by=existing.requested_by,
            decision=decision,
            reviewed_by=ctx.user_id,
            reason=reason,
            timestamp=now,
        )
        self._approvals[key] = updated

        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action=f"APPROVAL_{decision.value}",
            resource_type="Approval",
            resource_id=approval_id,
            details={"case_id": existing.case_id, "decision": decision.value, "reason": reason},
            correlation_id=correlation_id,
        )
        return updated

    def clear(self) -> None:
        """Reset for test fixtures."""
        self._cases.clear()
        self._approvals.clear()


case_service = CaseService()
