"""Structured AI findings and evidence provenance schemas for ResolveX AI.

PRD §9.5: Every investigation result must validate against strict Pydantic schemas.
All factual statements must cite one or more evidence IDs. Unsupported claims
must be marked as unknown.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_validator

from backend.app.domain.enums import PaymentStatus
from backend.app.domain.payment import BaseDomainModel


class InvestigationFinding(BaseDomainModel):
    """An individual grounded finding derived from verified evidence or deterministic rules."""

    code: str = Field(
        ...,
        description="Machine-readable finding code e.g. MISSING_PROVIDER_CONFIRMATION, SHARED_DEVICE_THRESHOLD_EXCEEDED",
    )
    statement: str = Field(
        ..., min_length=5, description="Clear explanatory statement grounded in cited evidence"
    )
    evidence_ids: list[str] = Field(
        ...,
        min_length=1,
        description="List of referenced evidence or event IDs backing this assertion",
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0"
    )
    uncertainty: str | None = Field(
        default=None, description="Explicit uncertainty or caveat if evidence is partial"
    )

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_citations(cls, ids: list[str]) -> list[str]:
        if not ids:
            raise ValueError(
                "Every factual finding must cite at least one evidence ID. Unsupported claims are prohibited."
            )
        cleaned = [item.strip() for item in ids if item and item.strip()]
        if not cleaned:
            raise ValueError("evidence_ids cannot contain only whitespace or empty strings.")
        return cleaned


class RecommendedNextStep(BaseDomainModel):
    """Action proposed by the agent or deterministic policy engine."""

    action: str = Field(
        ...,
        description="Action identifier e.g. VERIFY_PROVIDER_FINAL_STATUS, REQUEST_BANK_STATEMENT, DRAFT_REFUND_ESCALATION",
    )
    requires_human_approval: bool = Field(
        default=True, description="Whether this action requires human reviewer sign-off"
    )
    external_side_effect: bool = Field(
        default=False,
        description="Whether execution causes external financial/customer side effects",
    )
    action_payload: dict[str, str] = Field(
        default_factory=dict, description="Structured parameters for the action"
    )


class PaymentStateSummary(BaseDomainModel):
    """Authoritative snapshot of payment state at time of investigation."""

    normalized_status: PaymentStatus = Field(
        ..., description="Canonical status from authenticated provider events"
    )
    source: str = Field(..., description="Source of status e.g. provider_webhook, api_poll")
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModelMetadata(BaseDomainModel):
    """Provenance of the model run that assisted in the investigation."""

    provider: str = Field(..., description="gemma, gemini, or stub")
    model_id: str = Field(..., description="Model identifier or checkpoint name")
    prompt_version: str = Field(..., description="Version of the prompt/skill template used")
    execution_time_ms: int = Field(default=0, ge=0)


class StructuredInvestigationResult(BaseDomainModel):
    """Canonical investigation output contract specified in PRD §9.5."""

    case_id: str = Field(..., description="Unique case identifier")
    track: Literal["payment_issue", "fraud_investigation"] = Field(
        ..., description="Investigation track"
    )
    summary: str = Field(
        ..., min_length=10, description="Concise, evidence-grounded investigation overview"
    )
    payment_state: PaymentStateSummary = Field(
        ..., description="Current authoritative payment snapshot"
    )
    findings: list[InvestigationFinding] = Field(
        default_factory=list, description="Grounded factual findings"
    )
    unknowns: list[str] = Field(
        default_factory=list, description="Explicit list of unconfirmed facts or missing records"
    )
    recommended_next_step: RecommendedNextStep = Field(
        ..., description="Recommended operational action"
    )
    model_metadata: ModelMetadata = Field(..., description="Model provenance and prompt version")
