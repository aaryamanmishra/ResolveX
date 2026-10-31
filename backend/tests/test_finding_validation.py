"""Tests for PRD §9.5 structured AI findings schema and evidence citation enforcement."""

import pytest
from pydantic import ValidationError

from backend.app.domain.enums import PaymentStatus
from backend.app.domain.findings import (
    InvestigationFinding,
    ModelMetadata,
    PaymentStateSummary,
    RecommendedNextStep,
    StructuredInvestigationResult,
)


def test_investigation_finding_requires_evidence_citations() -> None:
    """PRD §6 (FR-018): Every factual finding must cite evidence IDs."""
    # Valid finding with citations
    finding = InvestigationFinding(
        code="MISSING_PROVIDER_CONFIRMATION",
        statement="No successful provider event is present in the retrieved event history.",
        evidence_ids=["evt_001", "evt_002"],
        confidence=0.95,
        uncertainty="Bank-side funds status not confirmed.",
    )
    assert len(finding.evidence_ids) == 2

    # Empty evidence IDs must raise validation error
    with pytest.raises(ValidationError):
        InvestigationFinding(
            code="UNSUPPORTED_CLAIM",
            statement="Payer was charged by bank.",
            evidence_ids=[],  # Prohibited
        )

    # Whitespace-only evidence IDs must raise error
    with pytest.raises(ValidationError):
        InvestigationFinding(
            code="UNSUPPORTED_CLAIM",
            statement="Payer was charged by bank.",
            evidence_ids=["   ", ""],
        )


def test_structured_investigation_result_schema() -> None:
    """PRD §9.5: Complete structured output contract."""
    result = StructuredInvestigationResult(
        case_id="case_demo_001",
        track="payment_issue",
        summary="Customer reports debited funds while payment gateway status is failed.",
        payment_state=PaymentStateSummary(
            normalized_status=PaymentStatus.FAILED,
            source="provider_webhook",
        ),
        findings=[
            InvestigationFinding(
                code="GATEWAY_REPORTED_FAILURE",
                statement="Gateway recorded failure code BAD_REQUEST_PAYMENT_TIMED_OUT.",
                evidence_ids=["evt_fail_99"],
            )
        ],
        unknowns=["bank_side_funds_status"],
        recommended_next_step=RecommendedNextStep(
            action="REQUEST_BANK_STATEMENT",
            requires_human_approval=True,
            external_side_effect=False,
        ),
        model_metadata=ModelMetadata(
            provider="stub",
            model_id="resolvex-stub-v1",
            prompt_version="payment-triage-v1",
        ),
    )
    assert result.track == "payment_issue"
    assert result.recommended_next_step.requires_human_approval is True
    assert result.unknowns == ["bank_side_funds_status"]
