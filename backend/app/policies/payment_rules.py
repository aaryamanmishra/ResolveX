"""Deterministic Payment Triage & Escalation Policy Engine for ResolveX AI.

PRD §6 (FR-003, FR-008, FR-020) & §15.1:
- Reconciles payment facts, funds status, and timeline events deterministically.
- Emits reproducible reason codes, policy citations, and operational recommendations.
- MANDATORY SAFETY INVARIANT: Any financial action or refund escalation MUST require
  explicit human review (requires_human_approval = True).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.app.domain.enums import FundsStatus, PaymentStatus, RefundStatus
from backend.app.domain.findings import RecommendedNextStep
from backend.app.domain.payment import Payment, PaymentEvent, Refund


@dataclass(frozen=True)
class PaymentPolicyRuleMatch:
    rule_name: str
    reason_code: str
    policy_citation: str
    evidence_ids: tuple[str, ...]
    explanation: str
    requires_human_approval: bool


@dataclass(frozen=True)
class PaymentEvaluationResult:
    case_id: str
    payment_id: str
    reason_codes: list[str]
    matched_rules: list[PaymentPolicyRuleMatch]
    evidence_ids: list[str]
    summary: str
    recommended_step: RecommendedNextStep
    requires_human_approval: bool
    unknowns: list[str]
    details: dict[str, Any]


class DeterministicPaymentPolicyEngine:
    """Evaluates payment discrepancies, SLA breaches, and unconfirmed debits deterministically."""

    def evaluate_payment(
        self,
        case_id: str,
        payment: Payment,
        timeline: list[PaymentEvent],
        refund: Refund | None = None,
    ) -> PaymentEvaluationResult:
        """Evaluate payment facts against operational policies."""
        matched_rules: list[PaymentPolicyRuleMatch] = []
        evidence_ids: set[str] = {payment.id}
        unknowns: list[str] = []

        for e in timeline:
            evidence_ids.add(e.id)
        if refund:
            evidence_ids.add(refund.id)

        now = datetime.now(timezone.utc)
        requires_approval = False
        action_name = "VERIFY_PROVIDER_FINAL_STATUS"
        action_payload: dict[str, str] = {}

        # ----------------------------------------------------------------------
        # Rule 1: Succeeded Payment (No discrepancy)
        # ----------------------------------------------------------------------
        if payment.payment_status == PaymentStatus.SUCCEEDED:
            matched_rules.append(
                PaymentPolicyRuleMatch(
                    rule_name="PAYMENT_CONFIRMED_SUCCESS",
                    reason_code="PAYMENT_SUCCEEDED",
                    policy_citation="REF-POL-01.1",
                    evidence_ids=(payment.id,),
                    explanation="Payment is confirmed SUCCEEDED by provider. No refund or intervention required.",
                    requires_human_approval=False,
                )
            )
            action_name = "RESOLVE_CASE"
            action_payload = {"resolution": "Payment verified successful by payment gateway."}

        # ----------------------------------------------------------------------
        # Rule 2: Unconfirmed Customer Debit Claim on Pending Payment
        # ----------------------------------------------------------------------
        elif (
            payment.payment_status in (PaymentStatus.PENDING, PaymentStatus.INITIATED)
            and payment.funds_status == FundsStatus.CUSTOMER_REPORTED_DEBIT
        ):
            matched_rules.append(
                PaymentPolicyRuleMatch(
                    rule_name="UNCONFIRMED_CUSTOMER_DEBIT_CLAIM",
                    reason_code="UNCONFIRMED_DEBIT_CLAIM",
                    policy_citation="REF-POL-01.2",
                    evidence_ids=(payment.id,),
                    explanation="Customer claims money was debited, but gateway status remains PENDING without provider confirmation.",
                    requires_human_approval=False,
                )
            )
            unknowns.append("bank_side_funds_status")
            action_name = "VERIFY_PROVIDER_FINAL_STATUS"
            action_payload = {"wait_window_hours": "24", "action": "poll_gateway"}

        # ----------------------------------------------------------------------
        # Rule 3: Payment Failed / Expired with Customer Debit Claim (Escalation)
        # ----------------------------------------------------------------------
        elif (
            payment.payment_status in (PaymentStatus.FAILED, PaymentStatus.EXPIRED)
            and payment.funds_status == FundsStatus.CUSTOMER_REPORTED_DEBIT
        ):
            matched_rules.append(
                PaymentPolicyRuleMatch(
                    rule_name="FAILED_PAYMENT_WITH_DEBIT_CLAIM",
                    reason_code="FAILED_PAYMENT_DEBITED",
                    policy_citation="REF-POL-01.3",
                    evidence_ids=(payment.id,),
                    explanation="Provider reports terminal FAILURE/EXPIRY, but customer claims funds debited. Investigation & statement verification required.",
                    requires_human_approval=True,
                )
            )
            unknowns.append("bank_reversal_status")
            requires_approval = True
            action_name = "DRAFT_REFUND_ESCALATION"
            action_payload = {
                "amount_minor": str(payment.amount_minor),
                "currency": payment.currency,
                "reason": "Customer reported debit on failed payment.",
            }

        # ----------------------------------------------------------------------
        # Rule 4: Refund SLA Breach (> 5 business days pending)
        # ----------------------------------------------------------------------
        if refund and refund.refund_status in (RefundStatus.REQUESTED, RefundStatus.PENDING):
            age_days = (now - refund.requested_at).total_seconds() / 86400.0
            if age_days > 5.0:
                matched_rules.append(
                    PaymentPolicyRuleMatch(
                        rule_name="REFUND_SLA_BREACH",
                        reason_code="REFUND_DELAY_EXCEEDS_SLA",
                        policy_citation="REF-POL-03.1",
                        evidence_ids=(refund.id,),
                        explanation=f"Refund {refund.id} has been pending for {age_days:.1f} days, exceeding the 5-day SLA.",
                        requires_human_approval=True,
                    )
                )
                requires_approval = True
                action_name = "ESCALATE_REFUND_TO_BANKING_OPS"
                action_payload = {
                    "refund_id": refund.id,
                    "age_days": f"{age_days:.1f}",
                    "sla_limit_days": "5",
                }

        # ----------------------------------------------------------------------
        # Rule 5: Generic Pending / Missing Provider Confirmation
        # ----------------------------------------------------------------------
        if not matched_rules:
            matched_rules.append(
                PaymentPolicyRuleMatch(
                    rule_name="MISSING_PROVIDER_CONFIRMATION",
                    reason_code="PENDING_GATEWAY_CONFIRMATION",
                    policy_citation="REF-POL-01.5",
                    evidence_ids=(payment.id,),
                    explanation="Transaction is pending confirmation from the payment provider.",
                    requires_human_approval=False,
                )
            )
            unknowns.append("provider_terminal_status")

        reason_codes = [m.reason_code for m in matched_rules]
        summary = "; ".join(m.explanation for m in matched_rules)

        recommended_step = RecommendedNextStep(
            action=action_name,
            requires_human_approval=requires_approval,
            external_side_effect=False,
            action_payload=action_payload,
        )

        return PaymentEvaluationResult(
            case_id=case_id,
            payment_id=payment.id,
            reason_codes=reason_codes,
            matched_rules=matched_rules,
            evidence_ids=sorted(evidence_ids),
            summary=summary,
            recommended_step=recommended_step,
            requires_human_approval=requires_approval,
            unknowns=unknowns,
            details={"rules_evaluated": len(matched_rules)},
        )


payment_policy_engine = DeterministicPaymentPolicyEngine()
