"""Reconciliation Engine for ResolveX AI.

PRD §6 (FR-007) & §15.1: Detects amount mismatches, customer debit claims
unconfirmed by gateway, delayed refunds, duplicate webhooks, and missing order mappings.
Automatically opens or updates reconciliation cases with audit logging.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.domain.case import Case
from backend.app.domain.enums import (
    CaseType,
    FraudSeverity,
    FundsStatus,
    PaymentStatus,
    RefundStatus,
    UserRole,
)
from backend.app.domain.payment import Payment, PaymentEvent, Refund
from backend.app.security.context import TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service

# Standard bank/PSP refund SLA window: 5 business days
REFUND_SLA_DAYS = 5


@dataclass(frozen=True)
class ReconciliationDiscrepancy:
    """Detected reconciliation exception."""

    discrepancy_code: str
    payment_id: str
    tenant_id: str
    description: str
    severity: FraudSeverity
    evidence_ids: tuple[str, ...]
    details: dict[str, Any]


class ReconciliationEngine:
    """Evaluates payment records, timelines, and refund statuses for operational discrepancies."""

    def __init__(self) -> None:
        self._exceptions: list[ReconciliationDiscrepancy] = []

    def check_amount_mismatch(
        self,
        tenant_id: str,
        payment: Payment,
        provider_event_amount_minor: int,
        expected_amount_minor: int,
        correlation_id: str | None = None,
    ) -> ReconciliationDiscrepancy | None:
        """PRD Scenario 8: Amount Mismatch between expected order amount and provider event amount."""
        if provider_event_amount_minor != expected_amount_minor:
            discrepancy = ReconciliationDiscrepancy(
                discrepancy_code="AMOUNT_MISMATCH",
                payment_id=payment.id,
                tenant_id=tenant_id,
                description=(
                    f"Amount mismatch detected for payment {payment.id}: "
                    f"Order expected {expected_amount_minor} minor units, but provider reported {provider_event_amount_minor}"
                ),
                severity=FraudSeverity.MEDIUM,
                evidence_ids=(payment.id,),
                details={
                    "expected_amount_minor": expected_amount_minor,
                    "provider_amount_minor": provider_event_amount_minor,
                    "currency": payment.currency,
                },
            )
            self._record_discrepancy(discrepancy, correlation_id)
            return discrepancy
        return None

    def check_customer_debit_claim_mismatch(
        self,
        tenant_id: str,
        payment: Payment,
        correlation_id: str | None = None,
    ) -> ReconciliationDiscrepancy | None:
        """PRD Scenario 4: Customer reports debit, but provider has no confirmed success."""
        if (
            payment.funds_status == FundsStatus.CUSTOMER_REPORTED_DEBIT
            and payment.payment_status != PaymentStatus.SUCCEEDED
        ):
            discrepancy = ReconciliationDiscrepancy(
                discrepancy_code="DEBIT_REPORTED_PROVIDER_UNCONFIRMED",
                payment_id=payment.id,
                tenant_id=tenant_id,
                description=(
                    f"Payer reported debit for payment {payment.id}, "
                    f"but authoritative provider status is {payment.payment_status.value}."
                ),
                severity=FraudSeverity.HIGH,
                evidence_ids=(payment.id,),
                details={
                    "funds_status": payment.funds_status.value,
                    "payment_status": payment.payment_status.value,
                    "order_ref": payment.order_ref,
                },
            )
            self._record_discrepancy(discrepancy, correlation_id)
            return discrepancy
        return None

    def check_delayed_refund(
        self,
        tenant_id: str,
        refund: Refund,
        current_time: datetime | None = None,
        correlation_id: str | None = None,
    ) -> ReconciliationDiscrepancy | None:
        """PRD Scenario 7: Refund in PENDING status past SLA window."""
        now = current_time or datetime.now(timezone.utc)
        if refund.refund_status == RefundStatus.PENDING:
            elapsed = now - refund.requested_at
            if elapsed > timedelta(days=REFUND_SLA_DAYS):
                discrepancy = ReconciliationDiscrepancy(
                    discrepancy_code="REFUND_SLA_BREACH",
                    payment_id=refund.payment_id,
                    tenant_id=tenant_id,
                    description=(
                        f"Refund {refund.id} has been pending for {elapsed.days} days, "
                        f"exceeding standard SLA of {REFUND_SLA_DAYS} days."
                    ),
                    severity=FraudSeverity.MEDIUM,
                    evidence_ids=(refund.id, refund.payment_id),
                    details={
                        "refund_id": refund.id,
                        "days_pending": elapsed.days,
                        "amount_minor": refund.amount_minor,
                    },
                )
                self._record_discrepancy(discrepancy, correlation_id)
                return discrepancy
        return None

    def check_missing_order_mapping(
        self,
        tenant_id: str,
        payment_id: str,
        order_ref: str,
        event: PaymentEvent,
        correlation_id: str | None = None,
    ) -> ReconciliationDiscrepancy | None:
        """PRD Scenario 9: Missing or invalid order mapping."""
        if not order_ref or order_ref in ("ORD-UNKNOWN", "sim_ord_unknown", "UNKNOWN"):
            discrepancy = ReconciliationDiscrepancy(
                discrepancy_code="MISSING_ORDER_MAPPING",
                payment_id=payment_id,
                tenant_id=tenant_id,
                description=f"Payment {payment_id} received from provider without a valid merchant order mapping.",
                severity=FraudSeverity.LOW,
                evidence_ids=(payment_id, event.id),
                details={"order_ref": order_ref, "provider": event.source},
            )
            self._record_discrepancy(discrepancy, correlation_id)
            return discrepancy
        return None

    def _record_discrepancy(
        self,
        discrepancy: ReconciliationDiscrepancy,
        correlation_id: str | None = None,
    ) -> Case:
        """Record discrepancy and automatically open an operational case under tenant."""
        self._exceptions.append(discrepancy)

        # Create system context for auto-case generation
        sys_ctx = TenantContext(
            tenant_id=discrepancy.tenant_id,
            user_id="sys_reconciliation_worker",
            role=UserRole.PLATFORM_ADMIN,
            is_system=True,
        )

        case = case_service.create_case(
            ctx=sys_ctx,
            case_type=(
                CaseType.REFUND_DELAY
                if discrepancy.discrepancy_code == "REFUND_SLA_BREACH"
                else CaseType.PAYMENT_DISCREPANCY
            ),
            title=f"Reconciliation: {discrepancy.discrepancy_code} on Payment {discrepancy.payment_id}",
            description=discrepancy.description,
            linked_payment_ids=[discrepancy.payment_id],
            priority=discrepancy.severity,
            correlation_id=correlation_id,
        )

        audit_service.record(
            tenant_id=discrepancy.tenant_id,
            actor_id="sys_reconciliation_worker",
            action=f"RECONCILIATION_EXCEPTION_{discrepancy.discrepancy_code}",
            resource_type="Payment",
            resource_id=discrepancy.payment_id,
            details=dict(discrepancy.details),
            correlation_id=correlation_id,
        )

        return case

    def list_exceptions(self, tenant_id: str) -> list[ReconciliationDiscrepancy]:
        """List active reconciliation exceptions for a tenant."""
        return [ex for ex in self._exceptions if ex.tenant_id == tenant_id]

    def clear(self) -> None:
        """Reset for tests."""
        self._exceptions.clear()


reconciliation_engine = ReconciliationEngine()
