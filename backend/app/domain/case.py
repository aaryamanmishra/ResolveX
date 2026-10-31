"""Case management, user, merchant, and approval domain models for ResolveX AI.

PRD §7.2: Represents operational cases, tenancy boundaries, and explicit human
approval records for sensitive financial actions.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from backend.app.domain.enums import (
    ApprovalDecision,
    CaseStatus,
    CaseType,
    FraudSeverity,
    UserRole,
)
from backend.app.domain.payment import BaseDomainModel


class Tenant(BaseDomainModel):
    """Tenant boundary representation."""

    id: str = Field(..., description="Unique tenant ID")
    name: str = Field(..., description="Display name of tenant organization")
    retention_days: int = Field(
        default=90, ge=1, le=3650, description="Data retention policy in days"
    )
    settings: dict[str, Any] = Field(
        default_factory=dict, description="Tenant configuration settings"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(BaseDomainModel):
    """User account within a tenant."""

    id: str = Field(..., description="Unique user ID")
    tenant_id: str = Field(..., description="Tenant identifier")
    role: UserRole = Field(..., description="Assigned RBAC role")
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User full name")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Merchant(BaseDomainModel):
    """Merchant organization entity."""

    id: str = Field(..., description="Internal merchant ID")
    tenant_id: str = Field(..., description="Tenant identifier")
    external_ref: str = Field(..., description="Merchant reference ID from external ERP/system")
    display_name: str = Field(..., description="Merchant brand or business name")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Case(BaseDomainModel):
    """Investigation or support triage case."""

    id: str = Field(..., description="Unique case reference e.g. CASE-2026-0001")
    tenant_id: str = Field(..., description="Tenant identifier")
    case_type: CaseType = Field(..., description="Classification of case")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="")
    linked_payment_ids: list[str] = Field(
        default_factory=list, description="IDs of connected payments"
    )
    priority: FraudSeverity = Field(
        default=FraudSeverity.LOW, description="Severity priority rating"
    )
    case_status: CaseStatus = Field(default=CaseStatus.NEW)
    owner_id: str | None = Field(default=None, description="Assigned analyst user ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Approval(BaseDomainModel):
    """Cryptographic/audit record for human-in-the-loop decision gate.

    PRD §6 (FR-020): Financially sensitive actions require explicit human review
    and are recorded separately from agent proposals.
    """

    id: str = Field(..., description="Unique approval ID")
    case_id: str = Field(..., description="Linked case identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    action_draft: dict[str, Any] = Field(
        ..., description="Proposed action payload e.g. REFUND_INITIATION_DRAFT"
    )
    requested_by: str = Field(..., description="Agent workflow or user ID that drafted the action")
    decision: ApprovalDecision = Field(default=ApprovalDecision.PENDING)
    reviewed_by: str | None = Field(default=None, description="Human reviewer user ID")
    reason: str | None = Field(default=None, description="Human review rationale or rejection note")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
