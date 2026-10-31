"""Comprehensive Phase 5 Acceptance Tests for Multimodal Evidence Intake.

PRD §5.3, §6 (FR-019), §7.2, §9.1, §13.1 & ANTIGRAVITY_BUILD_PLAN Phase 5 Gates:
1. Secure upload, magic bytes MIME verification, and SHA-256 content hashing.
2. Malware scanning: EICAR test string and malicious script tags quarantined.
3. Multimodal receipt image extraction: candidate claims with confidence and 2D bounding boxes.
4. Multimodal PDF bank statement extraction: debit claims with page and line location.
5. Multimodal audio voice note extraction: customer claims with audio timestamps.
6. Safety Invariant: Extracted claims CANNOT overwrite provider-confirmed payment status.
7. Privacy & Consent Gate: Gemini API fallback is consent-gated; identifiers are redacted.
8. User confirmation: User confirms or corrects candidate values, updating VerificationState.
9. Tenant boundary: Cross-tenant evidence access and confirmation fails closed.
10. REST API endpoints: presign, upload, claims, and confirmation.
"""

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.domain.enums import (
    CaseType,
    EvidenceSourceType,
    FundsStatus,
    PaymentStatus,
    UserRole,
    VerificationState,
)
from backend.app.domain.payment import Payment
from backend.app.main import app
from backend.app.providers.storage_provider import default_memory_storage
from backend.app.security.auth import create_access_token
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.case_service import case_service
from backend.app.services.evidence_service import evidence_service
from backend.app.services.malware_scanner import (
    EICAR_SIGNATURE,
    FileValidationError,
    MalwareDetectedError,
    malware_scanner,
)
from backend.app.services.multimodal_service import (
    ConsentRequiredError,
    multimodal_pipeline,
)
from backend.app.services.payment_service import payment_service


@pytest.fixture(autouse=True)
def clean_services() -> None:
    """Reset singletons between tests."""
    case_service.clear()
    payment_service.clear()
    evidence_service.clear()
    default_memory_storage.clear()


@pytest.fixture
def tenant_a_ctx() -> TenantContext:
    return TenantContext(
        tenant_id="tenant_evidence_a",
        user_id="user_analyst_a",
        role=UserRole.SUPPORT_ANALYST,
    )


@pytest.fixture
def tenant_b_ctx() -> TenantContext:
    return TenantContext(
        tenant_id="tenant_evidence_b",
        user_id="user_analyst_b",
        role=UserRole.SUPPORT_ANALYST,
    )


# Sample valid headers for magic bytes check
SAMPLE_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
SAMPLE_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50
SAMPLE_PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + b"1 0 obj\n<<>>\nendobj\n" * 10
SAMPLE_OGG_BYTES = b"OggS\x00\x02\x00\x00\x00\x00" + b"\x00" * 50


# ==============================================================================
# Gate 1: MIME Magic Byte Validation and SHA-256 Content Hashing
# ==============================================================================


def test_mime_magic_bytes_validation_and_spoof_detection() -> None:
    """PRD §5.3: Magic bytes header check prevents extension/MIME spoofing."""
    # Valid PNG
    assert malware_scanner.detect_and_validate_mime(SAMPLE_PNG_BYTES, "image/png") == "image/png"

    # Valid JPEG
    assert malware_scanner.detect_and_validate_mime(SAMPLE_JPEG_BYTES, "image/jpeg") == "image/jpeg"

    # Valid PDF
    assert (
        malware_scanner.detect_and_validate_mime(SAMPLE_PDF_BYTES, "application/pdf")
        == "application/pdf"
    )

    # Valid Ogg Audio
    assert malware_scanner.detect_and_validate_mime(SAMPLE_OGG_BYTES, "audio/ogg") == "audio/ogg"

    # Spoofed file: Text file renamed or declared as image/png
    spoofed_bytes = b"Hello this is just a plain text file pretending to be an image"
    with pytest.raises(FileValidationError, match="Invalid or unrecognized file format"):
        malware_scanner.detect_and_validate_mime(spoofed_bytes, "image/png")


# ==============================================================================
# Gate 2: Malware Scanning & Quarantine
# ==============================================================================


def test_malware_detection_quarantines_eicar_and_scripts() -> None:
    """PRD §13.1: EICAR signatures and active scripts in evidence are detected and quarantined."""
    # 1. EICAR test string
    eicar_file = b"%PDF-1.4\n" + EICAR_SIGNATURE
    with pytest.raises(MalwareDetectedError, match="EICAR test string"):
        malware_scanner.scan_for_malware(eicar_file, "application/pdf")

    # 2. Executable binary headers
    elf_file = b"\x7fELF" + b"\x00" * 20
    with pytest.raises(MalwareDetectedError, match="Executable binary header"):
        malware_scanner.scan_for_malware(elf_file, "image/png")

    # 3. Active script injection in document
    script_file = b"%PDF-1.4\n<script>alert('xss')</script>"
    with pytest.raises(MalwareDetectedError, match="Embedded active script"):
        malware_scanner.scan_for_malware(script_file, "application/pdf")


# ==============================================================================
# Gate 3: Multimodal Receipt Image Extraction (Confidence & 2D Bounding Boxes)
# ==============================================================================


def test_receipt_image_extraction_with_bounding_boxes(tenant_a_ctx: TenantContext) -> None:
    """PRD §5.3: Receipt image yields candidate claims with confidence and 2D bounding box."""
    case = case_service.create_case(
        ctx=tenant_a_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="UPI Payment debited but order failed",
    )

    asset, claims = evidence_service.upload_and_process_evidence(
        ctx=tenant_a_ctx,
        case_id=case.id,
        file_name="upi_receipt.png",
        declared_mime="image/png",
        data=SAMPLE_PNG_BYTES,
        source_type=EvidenceSourceType.RECEIPT_IMAGE,
    )

    assert asset.id.startswith("evid_")
    assert asset.mime_type == "image/png"
    assert asset.scan_status == "CLEAN"
    assert len(asset.content_hash) == 64  # SHA-256 hex string

    # Check extracted claims
    assert len(claims) >= 2
    claim_dict = {c.field_name: c for c in claims}

    # Verify amount_minor claim
    assert "amount_minor" in claim_dict
    amt_claim = claim_dict["amount_minor"]
    assert amt_claim.candidate_value == "50000"
    assert 0.0 <= amt_claim.confidence <= 1.0
    assert amt_claim.verification_state == VerificationState.UNVERIFIED
    # 2D Bounding box must be present: [ymin, xmin, ymax, xmax]
    assert "box_2d" in amt_claim.source_location
    assert len(amt_claim.source_location["box_2d"]) == 4

    # Verify UTR / UPI reference number claim
    assert "utr" in claim_dict
    utr_claim = claim_dict["utr"]
    assert utr_claim.candidate_value.startswith("UPI")
    assert "box_2d" in utr_claim.source_location


# ==============================================================================
# Gate 4: Multimodal Bank Statement PDF Extraction (Page & Line Location)
# ==============================================================================


def test_bank_statement_pdf_extraction(tenant_a_ctx: TenantContext) -> None:
    """PRD §5.3: Bank statement PDF yields debit claim with page and line coordinates."""
    case = case_service.create_case(
        ctx=tenant_a_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Bank statement verification",
    )

    asset, claims = evidence_service.upload_and_process_evidence(
        ctx=tenant_a_ctx,
        case_id=case.id,
        file_name="statement.pdf",
        declared_mime="application/pdf",
        data=SAMPLE_PDF_BYTES,
        source_type=EvidenceSourceType.PDF_STATEMENT,
    )

    assert asset.mime_type == "application/pdf"
    assert len(claims) >= 1
    statement_claim = claims[0]
    assert "bank_statement_debit" in statement_claim.field_name
    assert statement_claim.confidence >= 0.8
    assert "page" in statement_claim.source_location
    assert "line" in statement_claim.source_location


# ==============================================================================
# Gate 5: Multimodal Audio Voice Note Extraction (Timestamps)
# ==============================================================================


def test_voice_note_audio_extraction(tenant_a_ctx: TenantContext) -> None:
    """PRD §5.3: Audio voice note yields customer statement with audio start/end timestamps."""
    case = case_service.create_case(
        ctx=tenant_a_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Customer voice note dispute",
    )

    asset, claims = evidence_service.upload_and_process_evidence(
        ctx=tenant_a_ctx,
        case_id=case.id,
        file_name="customer_voice.ogg",
        declared_mime="audio/ogg",
        data=SAMPLE_OGG_BYTES,
        source_type=EvidenceSourceType.VOICE_NOTE,
    )

    assert asset.mime_type == "audio/ogg"
    assert len(claims) >= 1
    audio_claim = claims[0]
    assert "customer_statement" in audio_claim.field_name
    assert "audio_start_sec" in audio_claim.source_location
    assert "audio_end_sec" in audio_claim.source_location
    assert (
        audio_claim.source_location["audio_end_sec"]
        > audio_claim.source_location["audio_start_sec"]
    )


# ==============================================================================
# Gate 6: Safety Invariant — Claims CANNOT Overwrite Payment Provider Status
# ==============================================================================


def test_extracted_claims_cannot_overwrite_payment_truth(tenant_a_ctx: TenantContext) -> None:
    """PRD §7.1 & ANTIGRAVITY_BUILD_PLAN Rule 6:

    Uploaded documents and model extraction produce claims, NEVER authoritative payment state.
    """
    now = datetime.now(timezone.utc)
    payment = Payment(
        id="pay_truth_001",
        tenant_id=tenant_a_ctx.tenant_id,
        merchant_id="merch_1",
        order_ref="ORD-TRUTH-01",
        provider="simulator",
        provider_payment_id="sim_pay_01",
        amount_minor=50000,
        currency="INR",
        payment_status=PaymentStatus.FAILED,  # Provider truth is FAILED
        funds_status=FundsStatus.NOT_REPORTED,
        created_at=now,
        updated_at=now,
    )
    payment_service._payments[(tenant_a_ctx.tenant_id, payment.id)] = payment

    case = case_service.create_case(
        ctx=tenant_a_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Failed payment with receipt uploaded",
        linked_payment_ids=[payment.id],
    )

    # Customer uploads screenshot showing "Payment Succeeded"
    _, claims = evidence_service.upload_and_process_evidence(
        ctx=tenant_a_ctx,
        case_id=case.id,
        file_name="receipt_success_claim.png",
        declared_mime="image/png",
        data=SAMPLE_PNG_BYTES,
        source_type=EvidenceSourceType.RECEIPT_IMAGE,
    )

    # Verify provider truth is unchanged
    refetched_payment = payment_service.get_payment(tenant_a_ctx, payment.id)
    assert refetched_payment.payment_status == PaymentStatus.FAILED

    # Claims are marked UNVERIFIED
    for c in claims:
        assert c.verification_state == VerificationState.UNVERIFIED


# ==============================================================================
# Gate 7: Privacy & Consent Gate — Gemini API Routing & Identifier Redaction
# ==============================================================================


def test_gemini_api_consent_gate_and_redaction(tenant_a_ctx: TenantContext) -> None:
    """PRD §9.1 & §13.2: External Gemini API is consent-gated; identifiers are redacted."""
    case = case_service.create_case(
        ctx=tenant_a_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="External routing consent test",
    )

    # 1. Calling with force_gemini=True without consent MUST fail closed
    with pytest.raises(ConsentRequiredError, match="Explicit customer/tenant consent is required"):
        evidence_service.upload_and_process_evidence(
            ctx=tenant_a_ctx,
            case_id=case.id,
            file_name="doc.pdf",
            declared_mime="application/pdf",
            data=SAMPLE_PDF_BYTES,
            source_type=EvidenceSourceType.PDF_STATEMENT,
            consent_granted=False,
            force_gemini=True,
        )

    # 2. Identifier redaction test
    unredacted = "Account 123456789012 and phone 9876543210 transferred INR 500.00"
    redacted = multimodal_pipeline.redact_sensitive_identifiers(unredacted)
    assert "123456789012" not in redacted
    assert "XXXXXXXX9012" in redacted
    assert "9876543210" not in redacted
    assert "XXXXXX3210" in redacted


# ==============================================================================
# Gate 8: User Confirmation Workflow
# ==============================================================================


def test_user_confirmation_of_candidate_claims(tenant_a_ctx: TenantContext) -> None:
    """PRD §5.3 & §6 (FR-019): User/analyst confirms or rejects candidate extracted values."""
    case = case_service.create_case(
        ctx=tenant_a_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Confirmation workflow test",
    )

    _, claims = evidence_service.upload_and_process_evidence(
        ctx=tenant_a_ctx,
        case_id=case.id,
        file_name="receipt.png",
        declared_mime="image/png",
        data=SAMPLE_PNG_BYTES,
        source_type=EvidenceSourceType.RECEIPT_IMAGE,
    )

    claim = claims[0]
    assert claim.verification_state == VerificationState.UNVERIFIED

    # 1. User confirms claim
    confirmed = evidence_service.confirm_claim(
        ctx=tenant_a_ctx,
        claim_id=claim.id,
        decision=VerificationState.USER_CONFIRMED,
        confirmed_value="50000",
    )
    assert confirmed.verification_state == VerificationState.USER_CONFIRMED
    assert confirmed.confidence == 1.0

    # 2. User rejects another claim
    if len(claims) > 1:
        rejected = evidence_service.confirm_claim(
            ctx=tenant_a_ctx,
            claim_id=claims[1].id,
            decision=VerificationState.REJECTED,
        )
        assert rejected.verification_state == VerificationState.REJECTED


# ==============================================================================
# Gate 9: Cross-Tenant Isolation Fails Closed
# ==============================================================================


def test_cross_tenant_evidence_access_fails_closed(
    tenant_a_ctx: TenantContext, tenant_b_ctx: TenantContext
) -> None:
    """PRD §6 (FR-002): Actor from Tenant B cannot access or confirm evidence from Tenant A."""
    case_a = case_service.create_case(
        ctx=tenant_a_ctx,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Tenant A Private Evidence",
    )

    asset_a, claims_a = evidence_service.upload_and_process_evidence(
        ctx=tenant_a_ctx,
        case_id=case_a.id,
        file_name="private_a.png",
        declared_mime="image/png",
        data=SAMPLE_PNG_BYTES,
        source_type=EvidenceSourceType.RECEIPT_IMAGE,
    )

    # Tenant B tries to get asset from Tenant A
    with pytest.raises(SecurityError, match="Cross-tenant access forbidden"):
        evidence_service.get_evidence_asset(tenant_b_ctx, asset_a.id)

    # Tenant B tries to confirm claim from Tenant A
    with pytest.raises(SecurityError, match="Cross-tenant access forbidden"):
        evidence_service.confirm_claim(
            ctx=tenant_b_ctx,
            claim_id=claims_a[0].id,
            decision=VerificationState.USER_CONFIRMED,
        )


# ==============================================================================
# Gate 10: FastAPI REST Endpoints Integration
# ==============================================================================


def test_evidence_rest_api_endpoints(tenant_a_ctx: TenantContext) -> None:
    """PRD §11: Verify presign, upload, get detail, list claims, and confirm endpoints."""
    client = TestClient(app)
    token = create_access_token(
        user_id=tenant_a_ctx.user_id,
        tenant_id=tenant_a_ctx.tenant_id,
        role=tenant_a_ctx.role,
        email="analyst@tenant-a.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a case
    case_resp = client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "case_type": "PAYMENT_DISCREPANCY",
            "title": "Evidence API case",
            "linked_payment_ids": [],
        },
    )
    assert case_resp.status_code == 201
    case_id = case_resp.json()["id"]

    # 2. Presign upload URL endpoint
    presign_resp = client.post(
        "/api/v1/evidence/presign",
        headers=headers,
        json={
            "case_id": case_id,
            "file_name": "receipt.png",
            "mime_type": "image/png",
            "source_type": "RECEIPT_IMAGE",
        },
    )
    assert presign_resp.status_code == 200
    presign_data = presign_resp.json()
    assert "upload_url" in presign_data
    assert "evidence_id" in presign_data

    # 3. Direct upload endpoint (multipart/form-data)
    files = {"file": ("receipt.png", io.BytesIO(SAMPLE_PNG_BYTES), "image/png")}
    data = {
        "case_id": case_id,
        "source_type": "RECEIPT_IMAGE",
        "consent_granted": "true",
    }
    upload_resp = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        data=data,
        files=files,
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    evidence_id = upload_data["asset"]["id"]
    assert "download_url" in upload_data
    assert len(upload_data["claims"]) > 0
    claim_id = upload_data["claims"][0]["id"]

    # 4. Get evidence detail endpoint
    detail_resp = client.get(
        f"/api/v1/evidence/{evidence_id}",
        headers=headers,
    )
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["asset"]["id"] == evidence_id

    # 5. Get claims endpoint
    claims_resp = client.get(
        f"/api/v1/evidence/{evidence_id}/claims",
        headers=headers,
    )
    assert claims_resp.status_code == 200
    assert len(claims_resp.json()) > 0

    # 6. Confirm claim endpoint
    confirm_resp = client.post(
        f"/api/v1/evidence/{evidence_id}/confirm",
        headers=headers,
        json={
            "claim_id": claim_id,
            "decision": "USER_CONFIRMED",
            "confirmed_value": "50000",
        },
    )
    assert confirm_resp.status_code == 200
    confirmed_data = confirm_resp.json()
    assert confirmed_data["verification_state"] == "USER_CONFIRMED"
