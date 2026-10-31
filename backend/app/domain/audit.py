"""Audit trail and agent execution provenance models for ResolveX AI.

PRD §6 (FR-021) & §7.2: Immutable audit trail logging actor, tenant, case, action,
timestamp, policy/model/skill versions, and relevant evidence references.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from backend.app.domain.payment import BaseDomainModel


class AuditEvent(BaseDomainModel):
    """Immutable audit record."""

    id: str = Field(..., description="Unique audit event ID e.g. AUDIT-2026-0001")
    tenant_id: str = Field(..., description="Tenant boundary")
    actor_id: str = Field(..., description="User ID, agent workflow, or system process")
    action: str = Field(
        ...,
        description="Action performed e.g. CASE_STATUS_UPDATED, APPROVAL_GRANTED, WEBHOOK_INGESTED",
    )
    resource_type: str = Field(
        ..., description="Resource category e.g. Payment, Case, Approval, EvidenceAsset"
    )
    resource_id: str = Field(..., description="Target entity ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata_hash: str = Field(
        ..., description="SHA-256 hash of event metadata for tamper verification"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Structured event context (no PII or secrets)"
    )


class AgentRun(BaseDomainModel):
    """Execution telemetry and tracking for agent workflows."""

    id: str = Field(..., description="Unique agent run execution ID")
    case_id: str = Field(..., description="Associated case ID")
    workflow: str = Field(
        ..., description="Workflow identifier e.g. payment_triage, fraud_investigation"
    )
    skill_versions: list[str] = Field(
        default_factory=list, description="List of skill versions loaded e.g. payment-triage@1.0.0"
    )
    model_provider: str = Field(..., description="Provider: gemma, gemini, stub")
    model_id: str = Field(..., description="Model identifier")
    prompt_version: str = Field(..., description="Prompt template version tag")
    tool_trace_ids: list[str] = Field(
        default_factory=list, description="IDs of tools invoked during this run"
    )
    status: str = Field(
        default="COMPLETED",
        description="Run status: RUNNING, COMPLETED, FAILED, PAUSED_FOR_APPROVAL",
    )
    latency_ms: int = Field(
        default=0, ge=0, description="End-to-end execution latency in milliseconds"
    )
