"""Evidence assets and candidate claim models for ResolveX AI.

PRD §5.3 & §7.2: Multimodal intake creates EvidenceAssets. Models extract
candidate claims with confidence and bounding coordinates. Candidate claims
do NOT overwrite provider-confirmed truth.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import Field, field_validator

from backend.app.domain.enums import EvidenceSourceType, VerificationState
from backend.app.domain.payment import BaseDomainModel


class EvidenceAsset(BaseDomainModel):
    """Uploaded or ingested evidence artifact (receipt screenshot, bank statement PDF, voice note)."""

    id: str = Field(..., description="Unique evidence asset ID e.g. EVID-2026-0001")
    tenant_id: str = Field(..., description="Tenant identifier")
    case_id: str = Field(..., description="Linked case identifier")
    storage_key: str = Field(..., description="Object storage key within private bucket")
    mime_type: str = Field(
        ..., description="Verified MIME type e.g. image/png, application/pdf, audio/ogg"
    )
    file_size_bytes: int = Field(..., gt=0, description="Size of asset in bytes")
    content_hash: str = Field(..., description="SHA-256 hash of raw evidence file")
    source_type: EvidenceSourceType = Field(..., description="Type of evidence artifact")
    scan_status: str = Field(
        default="CLEAN", description="Antivirus scan status: PENDING, CLEAN, QUARANTINED"
    )
    retention_until: datetime = Field(..., description="Timestamp after which asset is purged")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceClaim(BaseDomainModel):
    """Candidate field extracted from an evidence asset.

    PRD §5.3: The extractor returns candidate fields, confidence, and page/crop references.
    Confirmed values serve as search hints; they do NOT overwrite provider-confirmed facts.
    """

    id: str = Field(..., description="Unique claim ID e.g. CLAIM-001")
    evidence_asset_id: str = Field(..., description="Linked evidence asset")
    field_name: str = Field(
        ..., description="Extracted field name e.g. amount_minor, utr, merchant_name, date_time"
    )
    candidate_value: str = Field(..., description="Extracted raw string value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model extraction confidence score")
    verification_state: VerificationState = Field(default=VerificationState.UNVERIFIED)
    source_location: dict[str, Any] = Field(
        default_factory=dict,
        description="Coordinates, page number, or audio timestamp bounding the claim",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return round(v, 4)
