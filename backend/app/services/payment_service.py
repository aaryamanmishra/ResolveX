"""Payment Ingestion, Status Normalization, and Timeline Service for ResolveX AI.

PRD §6 (FR-004 to FR-008) & §15.1:
- Signed webhook verification using exact raw body.
- Deduplication via idempotency keys (prevents duplicate state application).
- Append-only event timeline.
- Out-of-order event handling without terminal state regression.
- Explicit separation of provider truth vs customer claims.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.app.domain.enums import FraudSeverity, FundsStatus, PaymentStatus, RefundStatus
from backend.app.domain.payment import (
    CreatePaymentRequest,
    Payment,
    PaymentEvent,
    ProviderEventPayload,
    Refund,
)
from backend.app.providers.payment_provider import (
    PaymentProviderAdapter,
    SimulatorPaymentProvider,
)
from backend.app.providers.razorpay_provider import RazorpayPaymentProvider
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.reconciliation_service import (
    ReconciliationDiscrepancy,
    reconciliation_engine,
)

TERMINAL_PAYMENT_STATUSES = {
    PaymentStatus.SUCCEEDED,
    PaymentStatus.FAILED,
    PaymentStatus.EXPIRED,
    PaymentStatus.REVERSED,
}


@dataclass(frozen=True)
class IngestWebhookResult:
    """Outcome of processing an incoming signed webhook."""

    status: str  # "PROCESSED", "DUPLICATE_ACKNOWLEDGED", "FAILED"
    provider: str
    provider_event_id: str
    idempotency_key: str
    is_duplicate: bool
    payment_id: str
    normalized_status: PaymentStatus
    event_id: str
    message: str


class PaymentService:
    """Manages payments, append-only timelines, refunds, and webhook ingestion."""

    def __init__(self) -> None:
        # In-memory stores:
        # (tenant_id, payment_id) -> Payment
        self._payments: dict[tuple[str, str], Payment] = {}
        # (tenant_id, order_ref) -> payment_id (index)
        self._order_index: dict[tuple[str, str], str] = {}
        # (provider, provider_payment_id) -> (tenant_id, payment_id)
        self._provider_payment_index: dict[tuple[str, str], tuple[str, str]] = {}
        # payment_id -> list of PaymentEvent
        self._timeline: dict[str, list[PaymentEvent]] = {}
        # idempotency_key -> timestamp
        self._processed_idempotency_keys: dict[str, datetime] = {}
        # (tenant_id, refund_id) -> Refund
        self._refunds: dict[tuple[str, str], Refund] = {}

        # Provider Adapters
        self.simulator_adapter = SimulatorPaymentProvider()
        self.razorpay_adapter = RazorpayPaymentProvider()

    def get_adapter(self, provider_name: str) -> PaymentProviderAdapter:
        """Resolve adapter for a provider name."""
        if provider_name.lower() == "razorpay":
            return self.razorpay_adapter
        return self.simulator_adapter

    def create_payment(
        self,
        ctx: TenantContext,
        request: CreatePaymentRequest,
        correlation_id: str | None = None,
    ) -> Payment:
        """Create a payment record and initiate gateway session."""
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        adapter = self.get_adapter(request.payment_method)
        provider_result = adapter.create_payment(request)

        payment = Payment(
            id=payment_id,
            tenant_id=ctx.tenant_id,
            merchant_id=request.merchant_id,
            order_ref=request.order_ref,
            provider=provider_result.provider,
            provider_payment_id=provider_result.provider_payment_id,
            amount_minor=request.amount_minor,
            currency=request.currency,
            payment_status=PaymentStatus.CREATED,
            funds_status=FundsStatus.NOT_REPORTED,
            created_at=now,
            updated_at=now,
        )

        self._payments[(ctx.tenant_id, payment_id)] = payment
        self._order_index[(ctx.tenant_id, request.order_ref)] = payment_id
        self._provider_payment_index[
            (provider_result.provider, provider_result.provider_payment_id)
        ] = (
            ctx.tenant_id,
            payment_id,
        )
        self._timeline[payment_id] = []

        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="PAYMENT_CREATED",
            resource_type="Payment",
            resource_id=payment_id,
            details={
                "order_ref": request.order_ref,
                "amount_minor": request.amount_minor,
                "currency": request.currency,
                "provider": provider_result.provider,
            },
            correlation_id=correlation_id,
        )

        return payment

    def get_payment(self, ctx: TenantContext, payment_id: str) -> Payment:
        """Retrieve payment with strict tenant isolation."""
        key = (ctx.tenant_id, payment_id)
        if key not in self._payments:
            # Check for cross-tenant breach attempt
            for (tid, pid), _ in self._payments.items():
                if pid == payment_id and tid != ctx.tenant_id:
                    raise SecurityError(
                        f"Cross-tenant access forbidden: Caller tenant '{ctx.tenant_id}' cannot view payment '{payment_id}'"
                    )
            raise KeyError(f"Payment '{payment_id}' not found in tenant '{ctx.tenant_id}'")
        return self._payments[key]

    def list_payments(
        self,
        ctx: TenantContext,
        payment_status: PaymentStatus | None = None,
        funds_status: FundsStatus | None = None,
        limit: int = 50,
    ) -> list[Payment]:
        """List payments strictly scoped to caller's tenant."""
        results = [
            p
            for (tid, _), p in self._payments.items()
            if tid == ctx.tenant_id
            and (payment_status is None or p.payment_status == payment_status)
            and (funds_status is None or p.funds_status == funds_status)
        ]
        return results[:limit]

    def get_timeline(self, ctx: TenantContext, payment_id: str) -> list[PaymentEvent]:
        """Get immutable event timeline for a payment in caller's tenant."""
        # Ensure payment belongs to caller's tenant
        self.get_payment(ctx, payment_id)
        events = self._timeline.get(payment_id, [])
        # Ordered by event_time ASC, received_at ASC
        return sorted(events, key=lambda e: (e.event_time, e.received_at))

    def ingest_webhook(
        self,
        provider_name: str,
        raw_body: bytes,
        headers: dict[str, str],
        tenant_id: str = "tenant_finops_01",
        expected_amount_minor: int | None = None,
        correlation_id: str | None = None,
    ) -> IngestWebhookResult:
        """Validate signature, deduplicate, append event, normalize state, and reconcile."""
        adapter = self.get_adapter(provider_name)

        # 1. Signature Verification
        if not adapter.verify_webhook_signature(raw_body, headers):
            raise SecurityError(
                f"Webhook signature verification failed for provider '{provider_name}'"
            )

        # 2. Parse canonical event payload
        event_payload: ProviderEventPayload = adapter.parse_webhook_event(raw_body, headers)
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        # 3. Idempotency Check (PRD Scenario 5: Duplicate Webhook)
        idempotency_key = f"{tenant_id}:{provider_name}:{event_payload.provider_event_id}"
        if idempotency_key in self._processed_idempotency_keys:
            # Duplicate webhook detected: acknowledge safely without re-applying state mutation
            audit_service.record(
                tenant_id=tenant_id,
                actor_id=f"provider_webhook:{provider_name}",
                action="WEBHOOK_DUPLICATE_SUPPRESSED",
                resource_type="PaymentEvent",
                resource_id=event_payload.provider_event_id,
                details={"idempotency_key": idempotency_key, "payload_hash": payload_hash},
                correlation_id=correlation_id,
            )
            return IngestWebhookResult(
                status="DUPLICATE_ACKNOWLEDGED",
                provider=provider_name,
                provider_event_id=event_payload.provider_event_id,
                idempotency_key=idempotency_key,
                is_duplicate=True,
                payment_id="previously_applied",
                normalized_status=event_payload.normalized_status,
                event_id="previously_applied",
                message="Duplicate event recognized via idempotency key and suppressed without state corruption.",
            )

        # 4. Find or Bind Payment Record
        lookup_key = (provider_name, event_payload.provider_payment_id)
        if lookup_key in self._provider_payment_index:
            _, payment_id = self._provider_payment_index[lookup_key]
            payment = self._payments[(tenant_id, payment_id)]
        else:
            # Check order index or create bound payment
            order_key = (tenant_id, event_payload.order_ref)
            if order_key in self._order_index:
                payment_id = self._order_index[order_key]
                payment = self._payments[(tenant_id, payment_id)]
            else:
                payment_id = f"pay_{uuid.uuid4().hex[:12]}"
                payment = Payment(
                    id=payment_id,
                    tenant_id=tenant_id,
                    merchant_id="mch_cloudstore",
                    order_ref=event_payload.order_ref,
                    provider=provider_name,
                    provider_payment_id=event_payload.provider_payment_id,
                    amount_minor=event_payload.amount_minor or 1000,
                    currency=event_payload.currency,
                    payment_status=PaymentStatus.CREATED,
                    funds_status=FundsStatus.NOT_REPORTED,
                )
                self._payments[(tenant_id, payment_id)] = payment
                self._order_index[order_key] = payment_id
                self._provider_payment_index[lookup_key] = (tenant_id, payment_id)
                self._timeline[payment_id] = []

        # 5. Out-of-Order Handling (PRD Scenario 6)
        # If payment is already terminal, non-terminal events cannot regress it
        incoming_status = event_payload.normalized_status
        current_status = payment.payment_status

        target_status = incoming_status
        if (
            current_status in TERMINAL_PAYMENT_STATUSES
            and incoming_status not in TERMINAL_PAYMENT_STATUSES
        ):
            # Retain terminal status, do not regress
            target_status = current_status

        # 6. Append Immutable PaymentEvent
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        payment_event = PaymentEvent(
            id=event_id,
            payment_id=payment_id,
            provider_event_id=event_payload.provider_event_id,
            event_type=event_payload.event_type,
            raw_status=event_payload.raw_status,
            normalized_status=incoming_status,
            source=f"webhook_{provider_name}",
            event_time=event_payload.event_time,
            received_at=now,
            payload_hash=payload_hash,
            idempotency_key=idempotency_key,
        )

        if payment_id not in self._timeline:
            self._timeline[payment_id] = []
        self._timeline[payment_id].append(payment_event)
        self._processed_idempotency_keys[idempotency_key] = now

        # 7. Update Payment Authoritative State
        new_funds_status = payment.funds_status
        if target_status == PaymentStatus.SUCCEEDED:
            new_funds_status = FundsStatus.PROVIDER_CONFIRMED_CREDIT

        updated_payment = Payment(
            id=payment.id,
            tenant_id=payment.tenant_id,
            merchant_id=payment.merchant_id,
            order_ref=payment.order_ref,
            provider=payment.provider,
            provider_payment_id=payment.provider_payment_id,
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            payment_status=target_status,
            funds_status=new_funds_status,
            created_at=payment.created_at,
            updated_at=now,
        )
        self._payments[(tenant_id, payment_id)] = updated_payment

        # 8. Run Reconciliation Engine Checks
        if expected_amount_minor or (payment.amount_minor and event_payload.amount_minor):
            reconciliation_engine.check_amount_mismatch(
                tenant_id=tenant_id,
                payment=updated_payment,
                provider_event_amount_minor=event_payload.amount_minor,
                expected_amount_minor=expected_amount_minor or payment.amount_minor,
                correlation_id=correlation_id,
            )

        reconciliation_engine.check_missing_order_mapping(
            tenant_id=tenant_id,
            payment_id=payment_id,
            order_ref=updated_payment.order_ref,
            event=payment_event,
            correlation_id=correlation_id,
        )

        reconciliation_engine.check_customer_debit_claim_mismatch(
            tenant_id=tenant_id,
            payment=updated_payment,
            correlation_id=correlation_id,
        )

        # 9. Audit Event
        audit_service.record(
            tenant_id=tenant_id,
            actor_id=f"provider_webhook:{provider_name}",
            action="PAYMENT_STATUS_UPDATED",
            resource_type="Payment",
            resource_id=payment_id,
            details={
                "event_id": event_id,
                "provider_event_id": event_payload.provider_event_id,
                "old_status": current_status.value,
                "new_status": target_status.value,
                "payload_hash": payload_hash,
            },
            correlation_id=correlation_id,
        )

        return IngestWebhookResult(
            status="PROCESSED",
            provider=provider_name,
            provider_event_id=event_payload.provider_event_id,
            idempotency_key=idempotency_key,
            is_duplicate=False,
            payment_id=payment_id,
            normalized_status=target_status,
            event_id=event_id,
            message="Webhook ingested and state machine updated successfully.",
        )

    def report_customer_debit(
        self,
        ctx: TenantContext,
        payment_id: str,
        correlation_id: str | None = None,
    ) -> Payment:
        """PRD Scenario 4: Payer reports their account was debited.

        Sets funds_status=CUSTOMER_REPORTED_DEBIT separately from provider truth.
        """
        payment = self.get_payment(ctx, payment_id)

        updated_payment = Payment(
            id=payment.id,
            tenant_id=payment.tenant_id,
            merchant_id=payment.merchant_id,
            order_ref=payment.order_ref,
            provider=payment.provider,
            provider_payment_id=payment.provider_payment_id,
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            payment_status=payment.payment_status,  # Provider truth unmodified
            funds_status=FundsStatus.CUSTOMER_REPORTED_DEBIT,  # Separate claim
            created_at=payment.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._payments[(ctx.tenant_id, payment_id)] = updated_payment

        # Trigger reconciliation check
        reconciliation_engine.check_customer_debit_claim_mismatch(
            tenant_id=ctx.tenant_id,
            payment=updated_payment,
            correlation_id=correlation_id,
        )

        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="CUSTOMER_DEBIT_CLAIMED",
            resource_type="Payment",
            resource_id=payment_id,
            details={"funds_status": FundsStatus.CUSTOMER_REPORTED_DEBIT.value},
            correlation_id=correlation_id,
        )

        return updated_payment

    def record_refund(
        self,
        ctx: TenantContext,
        payment_id: str,
        provider_refund_id: str,
        amount_minor: int,
        status: RefundStatus = RefundStatus.PENDING,
        requested_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> Refund:
        """Record refund state and evaluate SLA window."""
        self.get_payment(ctx, payment_id)

        refund_id = f"ref_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        req_time = requested_at or now

        refund = Refund(
            id=refund_id,
            payment_id=payment_id,
            provider_refund_id=provider_refund_id,
            amount_minor=amount_minor,
            currency="INR",
            refund_status=status,
            requested_at=req_time,
            updated_at=now,
        )
        self._refunds[(ctx.tenant_id, refund_id)] = refund

        # Check for delayed refund
        reconciliation_engine.check_delayed_refund(
            tenant_id=ctx.tenant_id,
            refund=refund,
            current_time=now,
            correlation_id=correlation_id,
        )

        audit_service.record(
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="REFUND_RECORDED",
            resource_type="Refund",
            resource_id=refund_id,
            details={"amount_minor": amount_minor, "refund_status": status.value},
            correlation_id=correlation_id,
        )

        return refund

    def get_refund(self, ctx: TenantContext, refund_id: str) -> Refund:
        """Get refund record scoped to tenant."""
        key = (ctx.tenant_id, refund_id)
        if key not in self._refunds:
            raise KeyError(f"Refund '{refund_id}' not found in tenant '{ctx.tenant_id}'")
        return self._refunds[key]

    def simulate_scenario(
        self,
        ctx: TenantContext,
        scenario: str,
        amount_minor: int = 50000,
        currency: str = "INR",
        merchant_id: str = "merch_apex_01",
        correlation_id: str | None = None,
    ) -> tuple[Payment, PaymentEvent | None]:
        """Simulate a deterministic payment scenario and return payment with event."""
        order_ref = f"ORD-SIM-{uuid.uuid4().hex[:8].upper()}"
        payment_req = CreatePaymentRequest(
            tenant_id=ctx.tenant_id,
            merchant_id=merchant_id,
            order_ref=order_ref,
            amount_minor=amount_minor,
            currency=currency,
            customer_token=f"cust_tok_{ctx.user_id}",
        )
        payment = self.create_payment(ctx, payment_req, correlation_id=correlation_id)

        sim_adapter = SimulatorPaymentProvider()
        event: PaymentEvent | None = None

        if scenario in ("scenario_1_success", "success"):
            raw_body = json.dumps(
                {
                    "event_id": f"evt_sim_{uuid.uuid4().hex[:8]}",
                    "event_type": "payment.captured",
                    "payment_id": payment.provider_payment_id,
                    "order_ref": payment.order_ref,
                    "amount_minor": amount_minor,
                    "currency": currency,
                    "status": "captured",
                    "tenant_id": ctx.tenant_id,
                }
            ).encode("utf-8")
            sig = sim_adapter.generate_signature(raw_body)
            self.ingest_webhook(
                provider_name="simulator",
                raw_body=raw_body,
                headers={"X-Simulator-Signature": sig},
                tenant_id=ctx.tenant_id,
                correlation_id=correlation_id,
            )
            payment = self.get_payment(ctx, payment.id)
            timeline = self.get_timeline(ctx, payment.id)
            event = timeline[-1] if timeline else None

        elif scenario in ("scenario_2_pending", "pending"):
            pass

        elif scenario in ("scenario_3_failed", "failed"):
            raw_body = json.dumps(
                {
                    "event_id": f"evt_sim_{uuid.uuid4().hex[:8]}",
                    "event_type": "payment.failed",
                    "payment_id": payment.provider_payment_id,
                    "order_ref": payment.order_ref,
                    "amount_minor": amount_minor,
                    "currency": currency,
                    "status": "failed",
                    "tenant_id": ctx.tenant_id,
                }
            ).encode("utf-8")
            sig = sim_adapter.generate_signature(raw_body)
            self.ingest_webhook(
                provider_name="simulator",
                raw_body=raw_body,
                headers={"X-Simulator-Signature": sig},
                tenant_id=ctx.tenant_id,
                correlation_id=correlation_id,
            )
            payment = self.get_payment(ctx, payment.id)
            timeline = self.get_timeline(ctx, payment.id)
            event = timeline[-1] if timeline else None

        elif scenario in (
            "scenario_4_debit_mismatch",
            "scenario_4_customer_reported_debit",
            "debit_mismatch",
        ):
            raw_body = json.dumps(
                {
                    "event_id": f"evt_sim_{uuid.uuid4().hex[:8]}",
                    "event_type": "payment.failed",
                    "payment_id": payment.provider_payment_id,
                    "order_ref": payment.order_ref,
                    "amount_minor": amount_minor,
                    "currency": currency,
                    "status": "failed",
                    "tenant_id": ctx.tenant_id,
                }
            ).encode("utf-8")
            sig = sim_adapter.generate_signature(raw_body)
            self.ingest_webhook(
                provider_name="simulator",
                raw_body=raw_body,
                headers={"X-Simulator-Signature": sig},
                tenant_id=ctx.tenant_id,
                correlation_id=correlation_id,
            )
            payment = self.report_customer_debit(ctx, payment.id, correlation_id=correlation_id)
            discrepancy = ReconciliationDiscrepancy(
                discrepancy_code="UNCONFIRMED_CUSTOMER_DEBIT",
                payment_id=payment.id,
                tenant_id=ctx.tenant_id,
                description=f"Customer reported debit on payment {payment.id} while gateway status is {payment.payment_status.value}.",
                severity=FraudSeverity.MEDIUM,
                evidence_ids=(payment.id,),
                details={
                    "order_ref": payment.order_ref,
                    "provider_status": payment.payment_status.value,
                    "funds_status": payment.funds_status.value,
                    "amount_minor": payment.amount_minor,
                },
            )
            reconciliation_engine.record_discrepancy(discrepancy, correlation_id=correlation_id)
            timeline = self.get_timeline(ctx, payment.id)
            event = timeline[-1] if timeline else None

        elif scenario in ("scenario_6_out_of_order", "out_of_order"):
            raw1 = json.dumps(
                {
                    "event_id": f"evt_sim_cap_{uuid.uuid4().hex[:6]}",
                    "event_type": "payment.captured",
                    "payment_id": payment.provider_payment_id,
                    "order_ref": payment.order_ref,
                    "amount_minor": amount_minor,
                    "currency": currency,
                    "status": "captured",
                    "tenant_id": ctx.tenant_id,
                }
            ).encode("utf-8")
            self.ingest_webhook(
                "simulator",
                raw1,
                {"X-Simulator-Signature": sim_adapter.generate_signature(raw1)},
                tenant_id=ctx.tenant_id,
            )
            raw2 = json.dumps(
                {
                    "event_id": f"evt_sim_auth_{uuid.uuid4().hex[:6]}",
                    "event_type": "payment.authorized",
                    "payment_id": payment.provider_payment_id,
                    "order_ref": payment.order_ref,
                    "amount_minor": amount_minor,
                    "currency": currency,
                    "status": "authorized",
                    "tenant_id": ctx.tenant_id,
                }
            ).encode("utf-8")
            self.ingest_webhook(
                "simulator",
                raw2,
                {"X-Simulator-Signature": sim_adapter.generate_signature(raw2)},
                tenant_id=ctx.tenant_id,
            )
            payment = self.get_payment(ctx, payment.id)
            timeline = self.get_timeline(ctx, payment.id)
            event = timeline[-1] if timeline else None

        elif scenario in ("scenario_8_amount_mismatch", "amount_mismatch"):
            mismatch_amount = int(amount_minor * 0.9)
            raw_body = json.dumps(
                {
                    "event_id": f"evt_sim_{uuid.uuid4().hex[:8]}",
                    "event_type": "payment.captured",
                    "payment_id": payment.provider_payment_id,
                    "order_ref": payment.order_ref,
                    "amount_minor": mismatch_amount,
                    "currency": currency,
                    "status": "captured",
                    "tenant_id": ctx.tenant_id,
                }
            ).encode("utf-8")
            self.ingest_webhook(
                provider_name="simulator",
                raw_body=raw_body,
                headers={"X-Simulator-Signature": sim_adapter.generate_signature(raw_body)},
                tenant_id=ctx.tenant_id,
                expected_amount_minor=amount_minor,
                correlation_id=correlation_id,
            )
            payment = self.get_payment(ctx, payment.id)
            timeline = self.get_timeline(ctx, payment.id)
            event = timeline[-1] if timeline else None

        return payment, event

    def clear(self) -> None:
        """Reset for tests."""
        self._payments.clear()
        self._order_index.clear()
        self._provider_payment_index.clear()
        self._timeline.clear()
        self._processed_idempotency_keys.clear()
        self._refunds.clear()


payment_service = PaymentService()
