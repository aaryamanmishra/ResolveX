"""Evidence Management Service for ResolveX AI.

PRD §5.3, §6 (FR-019), §7.2 & §13.1:
- Presigned upload URL generation for private Spaces storage.
- File validation: magic byte headers, size limits, SHA-256 hash, and malware scan.
- Multimodal extraction orchestration (receipts, statements, voice notes).
- User confirmation workflow for candidate claims.
- Strict tenant isolation and tamper-evident audit trail logging.
- Safety Invariant: Uploaded claims NEVER overwrite provider-confirmed payment status.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.domain.enums import EvidenceSourceType, VerificationState
from backend.app.domain.evidence import EvidenceAsset, EvidenceClaim
from backend.app.providers.storage_provider import StorageProvider, get_storage_provider
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service
from backend.app.services.malware_scanner import malware_scanner
from backend.app.services.multimodal_service import multimodal_pipeline


class EvidenceService:
    """Manages the lifecycle of multimodal evidence assets and candidate claims."""

    def __init__(self, storage: StorageProvider | None = None) -> None:
        self.storage = storage or get_storage_provider()
        # Keyed by (tenant_id, evidence_id) -> EvidenceAsset
        self._assets: dict[tuple[str, str], EvidenceAsset] = {}
        # Keyed by (tenant_id, claim_id) -> EvidenceClaim
        self._claims: dict[tuple[str, str], EvidenceClaim] = {}
        # Index: (tenant_id, case_id) -> list of evidence_ids
        self._case_index: dict[tuple[str, str], list[str]] = {}
        # Index: (tenant_id, evidence_id) -> list of claim_ids
        self._asset_claim_index: dict[tuple[str, str], list[str]] = {}

    def presign_upload(
        self,
        ctx: TenantContext,
        case_id: str,
        file_name: str,
        mime_type: str,
        source_type: EvidenceSourceType,
        expires_in_seconds: int = 900,
    ) -> dict[str, Any]:
        """Generate a secure presigned upload URL for direct upload to private Spaces."""
        # 1. Enforce tenant access to case
        case_service.get_case(ctx, case_id)

        evidence_id = f"evid_{uuid.uuid4().hex[:12]}"
        storage_key = f"evidence/{case_id}/{evidence_id}_{file_name}"

        presigned_payload = self.storage.generate_presigned_upload_url(
            tenant_id=ctx.tenant_id,
            storage_key=storage_key,
            mime_type=mime_type,
            expires_in_seconds=expires_in_seconds,
        )

        presigned_payload["evidence_id"] = evidence_id
        presigned_payload["case_id"] = case_id
        presigned_payload["source_type"] = source_type.value

        return presigned_payload

    def upload_and_process_evidence(
        self,
        ctx: TenantContext,
        case_id: str,
        file_name: str,
        declared_mime: str,
        data: bytes,
        source_type: EvidenceSourceType,
        consent_granted: bool = False,
        force_gemini: bool = False,
        correlation_id: str | None = None,
    ) -> tuple[EvidenceAsset, list[EvidenceClaim]]:
        """Validate, malware-scan, store, hash, and extract multimodal claims from evidence bytes."""
        # 1. Tenant Case Verification
        case_service.get_case(ctx, case_id)

        # 2. Inspect Magic Bytes & Scan for Malware
        scan_result = malware_scanner.inspect_and_scan(data, declared_mime)

        # 3. Compute SHA-256 Hash of Evidence Data
        content_hash = hashlib.sha256(data).hexdigest()

        # 4. Generate Storage Key and Persist in Private Bucket
        evidence_id = f"evid_{uuid.uuid4().hex[:12]}"
        storage_key = f"evidence/{case_id}/{evidence_id}_{file_name}"
        self.storage.store_bytes(
            tenant_id=ctx.tenant_id,
            storage_key=storage_key,
            data=data,
            mime_type=scan_result.mime_type,
        )

        # 5. Build EvidenceAsset Entity (PRD §7.2)
        now = datetime.now(timezone.utc)
        retention_until = now + timedelta(days=90)

        asset = EvidenceAsset(
            id=evidence_id,
            tenant_id=ctx.tenant_id,
            case_id=case_id,
            storage_key=storage_key,
            mime_type=scan_result.mime_type,
            file_size_bytes=scan_result.file_size_bytes,
            content_hash=content_hash,
            source_type=source_type,
            scan_status=scan_result.scan_status,
            retention_until=retention_until,
            created_at=now,
        )

        self._assets[(ctx.tenant_id, evidence_id)] = asset
        self._case_index.setdefault((ctx.tenant_id, case_id), []).append(evidence_id)

        # 6. Run Multimodal Claim Extraction
        extracted_claims = multimodal_pipeline.extract_claims(
            asset=asset,
            raw_bytes=data,
            consent_granted=consent_granted,
            force_gemini=force_gemini,
        )

        # Store Extracted Claims
        claim_ids: list[str] = []
        for claim in extracted_claims:
            self._claims[(ctx.tenant_id, claim.id)] = claim
            claim_ids.append(claim.id)
        self._asset_claim_index[(ctx.tenant_id, evidence_id)] = claim_ids

        # 7. Record Immutable Audit Events
        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="EVIDENCE_UPLOADED",
            resource_type="EvidenceAsset",
            resource_id=evidence_id,
            details={
                "case_id": case_id,
                "file_name": file_name,
                "mime_type": scan_result.mime_type,
                "file_size_bytes": scan_result.file_size_bytes,
                "content_hash": content_hash,
                "claims_extracted": len(extracted_claims),
            },
            correlation_id=correlation_id,
        )

        return asset, extracted_claims

    def get_evidence_asset(
        self,
        ctx: TenantContext,
        evidence_id: str,
    ) -> tuple[EvidenceAsset, str]:
        """Retrieve evidence asset and generate short-lived presigned download URL."""
        key = (ctx.tenant_id, evidence_id)
        if key not in self._assets:
            # Check cross-tenant leakage
            for (tid, eid), _ in self._assets.items():
                if eid == evidence_id and tid != ctx.tenant_id:
                    raise SecurityError(
                        f"Cross-tenant access forbidden: Actor tenant '{ctx.tenant_id}' cannot view evidence '{evidence_id}'"
                    )
            raise KeyError(f"Evidence asset '{evidence_id}' not found in tenant '{ctx.tenant_id}'")

        asset = self._assets[key]
        download_url = self.storage.generate_presigned_download_url(
            tenant_id=ctx.tenant_id,
            storage_key=asset.storage_key,
            expires_in_seconds=3600,
        )
        return asset, download_url

    def list_evidence_for_case(
        self,
        ctx: TenantContext,
        case_id: str,
    ) -> list[EvidenceAsset]:
        """List all evidence assets attached to a case within the tenant."""
        case_service.get_case(ctx, case_id)
        evidence_ids = self._case_index.get((ctx.tenant_id, case_id), [])
        return [
            self._assets[(ctx.tenant_id, eid)]
            for eid in evidence_ids
            if (ctx.tenant_id, eid) in self._assets
        ]

    def list_claims_for_asset(
        self,
        ctx: TenantContext,
        evidence_id: str,
    ) -> list[EvidenceClaim]:
        """Retrieve all extracted candidate claims for an evidence asset."""
        self.get_evidence_asset(ctx, evidence_id)
        claim_ids = self._asset_claim_index.get((ctx.tenant_id, evidence_id), [])
        return [
            self._claims[(ctx.tenant_id, cid)]
            for cid in claim_ids
            if (ctx.tenant_id, cid) in self._claims
        ]

    def confirm_claim(
        self,
        ctx: TenantContext,
        claim_id: str,
        decision: VerificationState,
        confirmed_value: str | None = None,
        correlation_id: str | None = None,
    ) -> EvidenceClaim:
        """User or analyst confirms, corrects, or rejects an extracted candidate value.

        PRD §5.3 & §13.2: Confirmed candidate values serve as query hints; they
        do NOT overwrite provider-confirmed payment status.
        """
        key = (ctx.tenant_id, claim_id)
        if key not in self._claims:
            for (tid, cid), _ in self._claims.items():
                if cid == claim_id and tid != ctx.tenant_id:
                    raise SecurityError(
                        f"Cross-tenant access forbidden: Actor tenant '{ctx.tenant_id}' cannot confirm claim '{claim_id}'"
                    )
            raise KeyError(f"Evidence claim '{claim_id}' not found in tenant '{ctx.tenant_id}'")

        existing = self._claims[key]
        final_value = confirmed_value if confirmed_value is not None else existing.candidate_value

        updated_claim = EvidenceClaim(
            id=existing.id,
            evidence_asset_id=existing.evidence_asset_id,
            field_name=existing.field_name,
            candidate_value=final_value,
            confidence=1.0 if decision == VerificationState.USER_CONFIRMED else existing.confidence,
            verification_state=decision,
            source_location=existing.source_location,
            created_at=existing.created_at,
        )

        self._claims[key] = updated_claim

        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action=f"EVIDENCE_CLAIM_{decision.value}",
            resource_type="EvidenceClaim",
            resource_id=claim_id,
            details={
                "field_name": existing.field_name,
                "original_value": existing.candidate_value,
                "final_value": final_value,
                "decision": decision.value,
            },
            correlation_id=correlation_id,
        )

        return updated_claim

    def clear(self) -> None:
        """Reset service for testing."""
        self._assets.clear()
        self._claims.clear()
        self._case_index.clear()
        self._asset_claim_index.clear()


evidence_service = EvidenceService()
