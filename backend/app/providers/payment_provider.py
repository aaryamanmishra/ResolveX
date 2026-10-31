"""Payment Provider Protocol and Simulator Adapter for ResolveX AI.

PRD §6 (FR-003) & §12.3: Decouples payment ingestion and status queries behind
PaymentProviderAdapter. Domain logic never imports provider SDKs directly.
API KEYS REQUIRED IN PRODUCTION:
- RAZORPAY_KEY_ID: Razorpay gateway API key id
- RAZORPAY_KEY_SECRET: Razorpay gateway API secret
- RAZORPAY_WEBHOOK_SECRET: Razorpay webhook signing secret
In demo/development mode, SimulatorPaymentProvider runs without any external keys.
"""

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from backend.app.domain.enums import PaymentStatus, RefundStatus
from backend.app.domain.payment import (
    CreatePaymentRequest,
    ProviderEventPayload,
    ProviderPaymentResult,
    ProviderRefundResult,
)


@runtime_checkable
class PaymentProviderAdapter(Protocol):
    """Protocol that all payment gateways (Razorpay, Simulator, etc.) must implement."""

    @property
    def provider_name(self) -> str:
        """Name of the payment provider."""
        ...

    def create_payment(self, request: CreatePaymentRequest) -> ProviderPaymentResult:
        """Initiate payment session or simulated order."""
        ...

    def get_payment_status(self, provider_payment_id: str) -> ProviderPaymentResult:
        """Query authoritative payment status directly from provider API."""
        ...

    def get_refund_status(self, provider_refund_id: str) -> ProviderRefundResult:
        """Query authoritative refund status directly from provider API."""
        ...

    def verify_webhook_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        """Verify HMAC signature of incoming webhook event payload."""
        ...

    def parse_webhook_event(self, raw_body: bytes, headers: dict[str, str]) -> ProviderEventPayload:
        """Parse raw webhook bytes and headers into canonical ProviderEventPayload."""
        ...


class SimulatorPaymentProvider:
    """In-memory deterministic payment simulator for demo and offline test environments.

    Zero paid credentials required. Supports simulated success, pending, and failure transitions.
    """

    def __init__(self, webhook_secret: str = "sim_webhook_secret_default_key") -> None:
        self._webhook_secret = webhook_secret.encode("utf-8")
        self._payments: dict[str, ProviderPaymentResult] = {}
        self._refunds: dict[str, ProviderRefundResult] = {}

    @property
    def provider_name(self) -> str:
        return "simulator"

    def seed_payment(self, payment: ProviderPaymentResult) -> None:
        """Seed payment state for deterministic test scenarios."""
        self._payments[payment.provider_payment_id] = payment

    def seed_refund(self, refund: ProviderRefundResult) -> None:
        """Seed refund state for deterministic test scenarios."""
        self._refunds[refund.provider_refund_id] = refund

    def create_payment(self, request: CreatePaymentRequest) -> ProviderPaymentResult:
        payment_id = f"sim_pay_{len(self._payments) + 1:05d}"
        now = datetime.now(timezone.utc)
        result = ProviderPaymentResult(
            provider="simulator",
            provider_payment_id=payment_id,
            order_ref=request.order_ref,
            amount_minor=request.amount_minor,
            currency=request.currency,
            raw_status="created",
            normalized_status=PaymentStatus.CREATED,
            event_time=now,
            raw_payload={"simulator_note": "Payment created in memory simulator"},
        )
        self._payments[payment_id] = result
        return result

    def get_payment_status(self, provider_payment_id: str) -> ProviderPaymentResult:
        if provider_payment_id in self._payments:
            return self._payments[provider_payment_id]

        # Default fallback for unknown query
        now = datetime.now(timezone.utc)
        return ProviderPaymentResult(
            provider="simulator",
            provider_payment_id=provider_payment_id,
            order_ref="unknown_order",
            amount_minor=1000,
            currency="INR",
            raw_status="pending",
            normalized_status=PaymentStatus.PENDING,
            event_time=now,
            raw_payload={},
        )

    def get_refund_status(self, provider_refund_id: str) -> ProviderRefundResult:
        if provider_refund_id in self._refunds:
            return self._refunds[provider_refund_id]

        now = datetime.now(timezone.utc)
        return ProviderRefundResult(
            provider="simulator",
            provider_refund_id=provider_refund_id,
            payment_id="sim_pay_00001",
            amount_minor=1000,
            currency="INR",
            raw_status="pending",
            normalized_status=RefundStatus.PENDING,
            updated_at=now,
            raw_payload={},
        )

    def generate_signature(self, raw_body: bytes) -> str:
        """Helper to generate valid signature for test webhook calls."""
        return hmac.new(self._webhook_secret, raw_body, hashlib.sha256).hexdigest()

    def verify_webhook_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        signature = headers.get("X-Simulator-Signature") or headers.get("x-simulator-signature")
        if not signature:
            return False
        expected = self.generate_signature(raw_body)
        return hmac.compare_digest(expected, signature)

    def parse_webhook_event(self, raw_body: bytes, headers: dict[str, str]) -> ProviderEventPayload:
        import json

        data = json.loads(raw_body.decode("utf-8"))
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        status_str = data.get("status", "pending").upper()
        norm_status = PaymentStatus.PENDING
        if status_str in [s.value for s in PaymentStatus]:
            norm_status = PaymentStatus(status_str)

        return ProviderEventPayload(
            provider="simulator",
            provider_event_id=data.get("event_id", f"sim_evt_{payload_hash[:8]}"),
            event_type=data.get("event_type", "payment.updated"),
            provider_payment_id=data.get("payment_id", "sim_pay_unknown"),
            order_ref=data.get("order_ref", "sim_ord_unknown"),
            amount_minor=int(data.get("amount_minor", 0)),
            currency=data.get("currency", "INR"),
            raw_status=data.get("status", "pending"),
            normalized_status=norm_status,
            event_time=datetime.now(timezone.utc),
            payload_hash=payload_hash,
            raw_payload=data,
        )
