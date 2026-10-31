"""Tenant context and security actor representation for ResolveX AI.

PRD §6 (FR-001 & FR-002): Enforces tenant isolation and actor permissions across
all operations, database repositories, graph queries, and MCP tool boundaries.
"""

from dataclasses import dataclass

from backend.app.domain.enums import UserRole


class SecurityError(Exception):
    """Raised on security violation (cross-tenant access, unauthorized role)."""

    pass


@dataclass(frozen=True)
class TenantContext:
    """Immutable context carried through request pipelines and background tasks."""

    tenant_id: str
    user_id: str
    role: UserRole
    is_system: bool = False

    def validate_tenant_access(self, target_tenant_id: str) -> None:
        """Fail closed if attempting to access another tenant's resources."""
        if self.tenant_id != target_tenant_id:
            raise SecurityError(
                f"Cross-tenant access forbidden: actor tenant '{self.tenant_id}' cannot access resource tenant '{target_tenant_id}'"
            )

    def require_role(self, *allowed_roles: UserRole) -> None:
        """Verify the actor possesses one of the authorized roles."""
        if self.role not in allowed_roles:
            raise SecurityError(
                f"Unauthorized role: actor role '{self.role}' is not in allowed roles: {[r.value for r in allowed_roles]}"
            )
