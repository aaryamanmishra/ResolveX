"""Tests for monetary representation invariants.

PRD §7.2: Store monetary amounts as integer minor units (paise/cents).
Never use floating-point arithmetic or float values for money.
"""

import pytest
from pydantic import ValidationError

from backend.app.domain.payment import Payment, Refund


def test_amount_minor_requires_integer() -> None:
    """Float amounts must be strictly rejected at schema boundary."""
    # Integer is valid
    p = Payment(
        id="pay_m1",
        tenant_id="t1",
        merchant_id="m1",
        order_ref="o1",
        provider="sim",
        provider_payment_id="p1",
        amount_minor=1500,  # 15.00 INR
    )
    assert p.amount_minor == 1500

    # Float must raise error
    with pytest.raises((ValidationError, TypeError)):
        Payment(
            id="pay_m2",
            tenant_id="t1",
            merchant_id="m1",
            order_ref="o2",
            provider="sim",
            provider_payment_id="p2",
            amount_minor=15.50,  # type: ignore[arg-type]
        )


def test_amount_minor_must_be_positive() -> None:
    """Non-positive amounts must be rejected."""
    with pytest.raises(ValidationError):
        Payment(
            id="pay_m3",
            tenant_id="t1",
            merchant_id="m1",
            order_ref="o3",
            provider="sim",
            provider_payment_id="p3",
            amount_minor=0,
        )

    with pytest.raises(ValidationError):
        Payment(
            id="pay_m4",
            tenant_id="t1",
            merchant_id="m1",
            order_ref="o4",
            provider="sim",
            provider_payment_id="p4",
            amount_minor=-500,
        )


def test_refund_amount_minor_invariants() -> None:
    """Refund amounts must follow the same strict integer minor rules."""
    ref = Refund(
        id="ref_01",
        payment_id="pay_m1",
        provider_refund_id="prv_ref_1",
        amount_minor=500,
    )
    assert ref.amount_minor == 500

    with pytest.raises((ValidationError, TypeError)):
        Refund(
            id="ref_02",
            payment_id="pay_m1",
            provider_refund_id="prv_ref_2",
            amount_minor=50.25,  # type: ignore[arg-type]
        )
