"""Canonical payment models and event entities for ResolveX AI.

PRD §7.2: Monetary amounts are stored as integer minor units (e.g. paise, cents)
with ISO 4217 currency codes. Floating point arithmetic for money is prohibited.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.enums import (
    FundsStatus,
    PaymentStatus,
    RefundStatus,
    SettlementStatus,
)


class BaseDomainModel(BaseModel):
    """Base Pydantic model with strict validation configuration."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class Payment(BaseDomainModel):
    """Canonical payment entity."""

    id: str = Field(..., description="Unique ResolveX payment ID")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    merchant_id: str = Field(..., description="Internal merchant ID")
    order_ref: str = Field(..., description="Merchant order reference")
    provider: str = Field(..., description="Payment provider identifier (e.g. razorpay, simulator)")
    provider_payment_id: str = Field(..., description="Provider gateway transaction ID")
    amount_minor: int = Field(..., gt=0, description="Amount in integer minor units (paise/cents)")
    currency: str = Field(
        default="INR", min_length=3, max_length=3, description="ISO 4217 currency code"
    )
    payment_status: PaymentStatus = Field(default=PaymentStatus.CREATED)
    funds_status: FundsStatus = Field(default=FundsStatus.NOT_REPORTED)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("amount_minor")
    @classmethod
    def validate_amount_minor(cls, v: Any) -> int:
        if not isinstance(v, int):
            raise TypeError("amount_minor must be an integer, floats are prohibited")
        if v <= 0:
            raise ValueError("amount_minor must be greater than zero")
        return v


class PaymentEvent(BaseDomainModel):
    """Immutable event received from a payment provider or system operation."""

    id: str = Field(..., description="Unique event identifier")
    payment_id: str = Field(..., description="Linked payment ID")
    provider_event_id: str = Field(..., description="External event identifier from provider")
    event_type: str = Field(
        ..., description="Provider event type e.g. payment.authorized, payment.captured"
    )
    raw_status: str = Field(..., description="Exact raw status reported by provider")
    normalized_status: PaymentStatus = Field(..., description="Canonical normalized payment status")
    source: str = Field(..., description="Event source e.g. provider_webhook, api_poll, simulator")
    event_time: datetime = Field(..., description="Timestamp asserted by provider")
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp recorded by ingestion",
    )
    payload_hash: str = Field(..., description="SHA-256 hash of raw webhook payload")
    idempotency_key: str = Field(..., description="Deduplication key (tenant:provider:event_id)")


class Refund(BaseDomainModel):
    """Canonical refund entity tracking reversal lifecycle."""

    id: str = Field(..., description="Unique ResolveX refund ID")
    payment_id: str = Field(..., description="Linked payment ID")
    provider_refund_id: str = Field(..., description="Provider refund transaction identifier")
    amount_minor: int = Field(..., gt=0, description="Refund amount in minor units")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    refund_status: RefundStatus = Field(default=RefundStatus.REQUESTED)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("amount_minor")
    @classmethod
    def validate_refund_minor(cls, v: Any) -> int:
        if not isinstance(v, int):
            raise TypeError("amount_minor must be an integer, floats are prohibited")
        if v <= 0:
            raise ValueError("amount_minor must be greater than zero")
        return v


class SettlementRecord(BaseDomainModel):
    """Merchant settlement ledger entry."""

    id: str = Field(..., description="Unique settlement record ID")
    merchant_id: str = Field(..., description="Merchant identifier")
    provider: str = Field(..., description="Settling provider")
    settlement_ref: str = Field(..., description="External settlement batch reference")
    amount_minor: int = Field(..., gt=0, description="Settled amount in minor units")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    settlement_status: SettlementStatus = Field(default=SettlementStatus.PENDING)
    settlement_time: datetime = Field(..., description="Settlement credit timestamp")


class CreatePaymentRequest(BaseDomainModel):
    """Request DTO to initiate or simulate a payment."""

    tenant_id: str
    merchant_id: str
    order_ref: str
    amount_minor: int = Field(..., gt=0)
    currency: str = "INR"
    customer_token: str
    payment_method: str = "upi"


class ProviderPaymentResult(BaseDomainModel):
    """Result returned by a payment provider adapter."""

    provider: str
    provider_payment_id: str
    order_ref: str
    amount_minor: int
    currency: str
    raw_status: str
    normalized_status: PaymentStatus
    event_time: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ProviderRefundResult(BaseDomainModel):
    """Result returned by a payment provider for refund queries."""

    provider: str
    provider_refund_id: str
    payment_id: str
    amount_minor: int
    currency: str
    raw_status: str
    normalized_status: RefundStatus
    updated_at: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ProviderEventPayload(BaseDomainModel):
    """Parsed webhook payload from any payment provider."""

    provider: str
    provider_event_id: str
    event_type: str
    provider_payment_id: str
    order_ref: str
    amount_minor: int
    currency: str
    raw_status: str
    normalized_status: PaymentStatus
    event_time: datetime
    payload_hash: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
