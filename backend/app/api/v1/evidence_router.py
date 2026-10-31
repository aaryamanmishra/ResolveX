"""Evidence Management and Multimodal Extraction API Endpoints for ResolveX AI.

PRD §11:
- POST /api/v1/evidence/presign: Request short-lived upload URL
- POST /api/v1/evidence/upload: Direct multipart upload & automated multimodal extraction
- GET  /api/v1/evidence/{evidence_id}: Retrieve evidence asset detail and presigned download URL
- GET  /api/v1/evidence/{evidence_id}/claims: List candidate claims with bounding locations
- POST /api/v1/evidence/{evidence_id}/confirm: User confirmation of candidate claims
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.domain.enums import EvidenceSourceType, UserRole, VerificationState
from backend.app.domain.evidence import EvidenceAsset, EvidenceClaim
from backend.app.security.auth import get_current_tenant_context, require_roles
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.evidence_service import evidence_service
from backend.app.services.malware_scanner import FileValidationError, MalwareDetectedError
from backend.app.services.multimodal_service import ConsentRequiredError

router = APIRouter(prefix="/evidence", tags=["Evidence"])


class PresignUploadRequest(BaseModel):
    case_id: str
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: str
    source_type: EvidenceSourceType = EvidenceSourceType.RECEIPT_IMAGE
    expires_in_seconds: int = Field(default=900, ge=60, le=3600)


class ConfirmClaimRequest(BaseModel):
    claim_id: str
    decision: VerificationState = VerificationState.USER_CONFIRMED
    confirmed_value: str | None = None


class EvidenceDetailResponse(BaseModel):
    asset: EvidenceAsset
    download_url: str
    claims: list[EvidenceClaim]


@router.post("/presign", status_code=status.HTTP_200_OK)
def presign_upload_url(
    req: PresignUploadRequest,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> dict:
    """Request a short-lived presigned upload URL for direct upload to private storage."""
    try:
        return evidence_service.presign_upload(
            ctx=ctx,
            case_id=req.case_id,
            file_name=req.file_name,
            mime_type=req.mime_type,
            source_type=req.source_type,
            expires_in_seconds=req.expires_in_seconds,
        )
    except SecurityError as sec_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(sec_err),
        ) from sec_err
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.post("/upload", response_model=EvidenceDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence_file(
    request: Request,
    case_id: str = Form(...),
    source_type: EvidenceSourceType = Form(...),
    consent_granted: bool = Form(default=False),
    force_gemini: bool = Form(default=False),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> EvidenceDetailResponse:
    """Direct multipart upload endpoint with MIME validation, malware scan, and multimodal extraction."""
    correlation_id = getattr(request.state, "correlation_id", None)
    file_bytes = await file.read()
    declared_mime = file.content_type or "application/octet-stream"

    try:
        asset, claims = evidence_service.upload_and_process_evidence(
            ctx=ctx,
            case_id=case_id,
            file_name=file.filename or "uploaded_file",
            declared_mime=declared_mime,
            data=file_bytes,
            source_type=source_type,
            consent_granted=consent_granted,
            force_gemini=force_gemini,
            correlation_id=correlation_id,
        )
        _, download_url = evidence_service.get_evidence_asset(ctx, asset.id)

        return EvidenceDetailResponse(
            asset=asset,
            download_url=download_url,
            claims=claims,
        )
    except MalwareDetectedError as mal_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Upload rejected: {mal_err}",
        ) from mal_err
    except FileValidationError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {val_err}",
        ) from val_err
    except ConsentRequiredError as con_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Consent Required: {con_err}",
        ) from con_err
    except SecurityError as sec_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(sec_err),
        ) from sec_err
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.get("/{evidence_id}", response_model=EvidenceDetailResponse)
def get_evidence_detail(
    evidence_id: str,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> EvidenceDetailResponse:
    """Retrieve evidence asset details, presigned download URL, and extracted claims."""
    try:
        asset, download_url = evidence_service.get_evidence_asset(ctx, evidence_id)
        claims = evidence_service.list_claims_for_asset(ctx, evidence_id)
        return EvidenceDetailResponse(
            asset=asset,
            download_url=download_url,
            claims=claims,
        )
    except SecurityError as sec_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(sec_err),
        ) from sec_err
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.get("/{evidence_id}/claims", response_model=list[EvidenceClaim])
def get_evidence_claims(
    evidence_id: str,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> list[EvidenceClaim]:
    """Retrieve extracted candidate claims with confidence scores and source locations."""
    try:
        return evidence_service.list_claims_for_asset(ctx, evidence_id)
    except SecurityError as sec_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(sec_err),
        ) from sec_err
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.post("/{evidence_id}/confirm", response_model=EvidenceClaim)
def confirm_evidence_claim(
    evidence_id: str,
    req: ConfirmClaimRequest,
    request: Request,
    ctx: TenantContext = Depends(
        require_roles(
            UserRole.CUSTOMER,
            UserRole.SUPPORT_ANALYST,
            UserRole.FRAUD_ANALYST,
            UserRole.SUPERVISOR,
            UserRole.PLATFORM_ADMIN,
        )
    ),
) -> EvidenceClaim:
    """User confirmation or correction of an extracted candidate claim."""
    correlation_id = getattr(request.state, "correlation_id", None)
    try:
        return evidence_service.confirm_claim(
            ctx=ctx,
            claim_id=req.claim_id,
            decision=req.decision,
            confirmed_value=req.confirmed_value,
            correlation_id=correlation_id,
        )
    except SecurityError as sec_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(sec_err),
        ) from sec_err
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
