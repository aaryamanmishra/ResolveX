"""Audit log API endpoints for ResolveX AI."""

from fastapi import APIRouter, Depends

from backend.app.domain.audit import AuditEvent
from backend.app.domain.enums import UserRole
from backend.app.security.auth import require_roles
from backend.app.security.context import TenantContext
from backend.app.services.audit_service import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=list[AuditEvent])
def list_audit_events(
    resource_type: str | None = None,
    limit: int = 100,
    ctx: TenantContext = Depends(
        require_roles(
            UserRole.SUPPORT_ANALYST,
            UserRole.FRAUD_ANALYST,
            UserRole.SUPERVISOR,
            UserRole.PLATFORM_ADMIN,
        )
    ),
) -> list[AuditEvent]:
    """List tamper-evident audit events scoped strictly to the current tenant."""
    return audit_service.list_events_for_tenant(
        tenant_id=ctx.tenant_id,
        resource_type=resource_type,
        limit=limit,
    )


@router.get("/resource/{resource_id}", response_model=list[AuditEvent])
def get_resource_audit_history(
    resource_id: str,
    limit: int = 50,
    ctx: TenantContext = Depends(
        require_roles(
            UserRole.SUPPORT_ANALYST,
            UserRole.FRAUD_ANALYST,
            UserRole.SUPERVISOR,
            UserRole.PLATFORM_ADMIN,
        )
    ),
) -> list[AuditEvent]:
    """Retrieve immutable audit trail for a specific resource ID within tenant boundary."""
    return audit_service.get_history(ctx=ctx, resource_id=resource_id, limit=limit)
