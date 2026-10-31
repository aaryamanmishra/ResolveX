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
        require_roles(UserRole.SUPERVISOR, UserRole.PLATFORM_ADMIN, UserRole.FRAUD_ANALYST)
    ),
) -> list[AuditEvent]:
    """List tamper-evident audit events scoped strictly to the current tenant."""
    return audit_service.list_events_for_tenant(
        tenant_id=ctx.tenant_id,
        resource_type=resource_type,
        limit=limit,
    )
