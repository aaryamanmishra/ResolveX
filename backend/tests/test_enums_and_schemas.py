"""Tests for domain enums, models, and schema validation invariants."""

import pytest
from pydantic import ValidationError

from backend.app.domain.case import Case, Tenant
from backend.app.domain.enums import (
    CaseStatus,
    CaseType,
    FraudSeverity,
    FundsStatus,
    PaymentStatus,
    RefundStatus,
    SettlementStatus,
)
from backend.app.domain.payment import Payment


def test_status_dimensions_remain_distinct() -> None:
    """PRD §7.1: Status dimensions must not be collapsed into one string."""
    # Ensure all enum values exist as specified
    assert PaymentStatus.SUCCEEDED == "SUCCEEDED"
    assert FundsStatus.CUSTOMER_REPORTED_DEBIT == "CUSTOMER_REPORTED_DEBIT"
    assert FundsStatus.PROVIDER_CONFIRMED_DEBIT == "PROVIDER_CONFIRMED_DEBIT"
    assert RefundStatus.PENDING == "PENDING"
    assert SettlementStatus.MISMATCH == "MISMATCH"
    assert CaseStatus.REVIEW_REQUIRED == "REVIEW_REQUIRED"
    assert FraudSeverity.CRITICAL == "CRITICAL"


def test_payment_model_strict_validation() -> None:
    """Payment model must forbid extra unknown fields and require strict types."""
    valid_payment = Payment(
        id="pay_001",
        tenant_id="tenant_01",
        merchant_id="mch_01",
        order_ref="ORD-101",
        provider="simulator",
        provider_payment_id="sim_101",
        amount_minor=10000,
        currency="INR",
        payment_status=PaymentStatus.PENDING,
        funds_status=FundsStatus.NOT_REPORTED,
    )
    assert valid_payment.amount_minor == 10000
    assert valid_payment.currency == "INR"

    # Forbid extra fields
    with pytest.raises(ValidationError):
        Payment(
            id="pay_002",
            tenant_id="tenant_01",
            merchant_id="mch_01",
            order_ref="ORD-102",
            provider="simulator",
            provider_payment_id="sim_102",
            amount_minor=5000,
            currency="INR",
            unauthorized_field="malicious_payload",  # Extra field
        )


def test_case_and_tenant_schemas() -> None:
    """Verify Case and Tenant creation."""
    tenant = Tenant(id="tenant_01", name="Test Org", retention_days=60)
    assert tenant.retention_days == 60

    case = Case(
        id="case_001",
        tenant_id=tenant.id,
        case_type=CaseType.PAYMENT_DISCREPANCY,
        title="Payment not credited",
        linked_payment_ids=["pay_001"],
        priority=FraudSeverity.MEDIUM,
    )
    assert case.priority == FraudSeverity.MEDIUM
    assert case.case_status == CaseStatus.NEW
