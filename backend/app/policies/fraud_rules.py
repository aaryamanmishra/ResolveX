"""Deterministic Fraud Rules Engine for ResolveX AI.

PRD §6 (FR-012) & §15.2:
- Evaluates graph neighborhoods using deterministic heuristics.
- Emits reproducible reason codes, severity levels, and evidence IDs.
- Prevents false positives: Benign shared device scenarios do NOT become automatic fraud verdicts.
- Mandatory human review required for Medium, High, and Critical findings.
"""

from dataclasses import dataclass
from typing import Any

from backend.app.domain.enums import FraudSeverity
from backend.app.domain.graph import GraphNeighborhood, VertexLabel

SHARED_DEVICE_THRESHOLD = 3
MULTI_INSTRUMENT_THRESHOLD = 3
VELOCITY_THRESHOLD = 4


@dataclass(frozen=True)
class FraudRuleMatch:
    rule_name: str
    reason_code: str
    severity: FraudSeverity
    evidence_ids: tuple[str, ...]
    explanation: str
    is_alert: bool


@dataclass(frozen=True)
class FraudEvaluationResult:
    case_id: str
    is_alert: bool
    severity: FraudSeverity
    reason_codes: list[str]
    matched_rules: list[FraudRuleMatch]
    evidence_ids: list[str]
    summary: str
    requires_human_review: bool
    details: dict[str, Any]


class DeterministicFraudRuleEngine:
    """Evaluates graph topology and transaction patterns deterministically."""

    def evaluate_neighborhood(
        self,
        case_id: str,
        neighborhood: GraphNeighborhood,
        threshold_shared_device: int = SHARED_DEVICE_THRESHOLD,
    ) -> FraudEvaluationResult:
        """Run deterministic rule suite over a bounded graph neighborhood."""
        matched_rules: list[FraudRuleMatch] = []
        all_evidence_ids: set[str] = set()

        vertices_by_label: dict[str, list] = {}
        for v in neighborhood.vertices:
            vertices_by_label.setdefault(v.label, []).append(v)

        device_vertices = vertices_by_label.get(VertexLabel.DEVICE_TOKEN, [])
        customer_vertices = vertices_by_label.get(VertexLabel.CUSTOMER_TOKEN, [])
        payment_vertices = vertices_by_label.get(VertexLabel.PAYMENT, [])
        instrument_vertices = vertices_by_label.get(VertexLabel.PAYMENT_INSTRUMENT_TOKEN, [])
        case_vertices = vertices_by_label.get(VertexLabel.CASE, [])

        # ----------------------------------------------------------------------
        # Rule 1 & Rule 2: Shared Device Analysis (Syndicate vs Benign)
        # ----------------------------------------------------------------------
        for dev in device_vertices:
            # Find customers linked to this device
            connected_customers = [
                e.source_id
                for e in neighborhood.edges
                if e.target_id == dev.id and e.label == "USED_DEVICE"
            ]
            unique_customers = list(set(connected_customers))
            cust_count = len(unique_customers)

            if cust_count > threshold_shared_device:
                # PRD Scenario 1: Fraud Syndicate Detected (> threshold)
                evidence = (dev.id, *unique_customers)
                rule_match = FraudRuleMatch(
                    rule_name="SHARED_DEVICE_SYNDICATE",
                    reason_code="SHARED_DEVICE_THRESHOLD_EXCEEDED",
                    severity=FraudSeverity.HIGH,
                    evidence_ids=evidence,
                    explanation=(
                        f"Device token {dev.id} is shared by {cust_count} distinct customer accounts, "
                        f"exceeding the fraud threshold of {threshold_shared_device}."
                    ),
                    is_alert=True,
                )
                matched_rules.append(rule_match)
                all_evidence_ids.update(evidence)

            elif 1 < cust_count <= 2:
                # PRD Scenario 5: Benign Shared Device Filter (e.g. Family Tablet)
                # Does NOT emit fraud alert, suppresses false positive
                evidence = (dev.id, *unique_customers)
                benign_match = FraudRuleMatch(
                    rule_name="BENIGN_SHARED_DEVICE_FILTER",
                    reason_code="BENIGN_SHARED_DEVICE_SUPPRESSED",
                    severity=FraudSeverity.NONE,
                    evidence_ids=evidence,
                    explanation=(
                        f"Device token {dev.id} is shared by {cust_count} accounts, "
                        "consistent with benign household/family sharing. Automated fraud alert suppressed."
                    ),
                    is_alert=False,
                )
                matched_rules.append(benign_match)

        # ----------------------------------------------------------------------
        # Rule 3: Repeated Low-Value Attempts Across Multiple Instruments
        # ----------------------------------------------------------------------
        if len(instrument_vertices) >= MULTI_INSTRUMENT_THRESHOLD and len(customer_vertices) >= 1:
            evidence = tuple(inst.id for inst in instrument_vertices)
            rule_match = FraudRuleMatch(
                rule_name="MULTI_INSTRUMENT_CARD_TESTING",
                reason_code="REPEATED_ATTEMPTS_MULTI_INSTRUMENTS",
                severity=FraudSeverity.HIGH,
                evidence_ids=evidence,
                explanation=(
                    f"Customer account connected to {len(instrument_vertices)} distinct payment instruments "
                    "in a single investigation window, indicating smurfing or card testing behavior."
                ),
                is_alert=True,
            )
            matched_rules.append(rule_match)
            all_evidence_ids.update(evidence)

        # ----------------------------------------------------------------------
        # Rule 4: High Transaction Velocity Burst
        # ----------------------------------------------------------------------
        if len(payment_vertices) >= VELOCITY_THRESHOLD:
            evidence = tuple(p.id for p in payment_vertices)
            rule_match = FraudRuleMatch(
                rule_name="TRANSACTION_VELOCITY_BURST",
                reason_code="UNUSUAL_TRANSACTION_VELOCITY",
                severity=FraudSeverity.MEDIUM,
                evidence_ids=evidence,
                explanation=(
                    f"Rapid burst of {len(payment_vertices)} transactions observed within the neighborhood window."
                ),
                is_alert=True,
            )
            matched_rules.append(rule_match)
            all_evidence_ids.update(evidence)

        # ----------------------------------------------------------------------
        # Rule 5: Connection to Prior Flagged Fraud Case
        # ----------------------------------------------------------------------
        prior_cases = [c for c in case_vertices if c.id != case_id]
        if prior_cases:
            evidence = tuple(c.id for c in prior_cases)
            rule_match = FraudRuleMatch(
                rule_name="LINKED_TO_PRIOR_FRAUD_CASE",
                reason_code="CONNECTED_TO_HISTORICAL_FRAUD_CASE",
                severity=FraudSeverity.CRITICAL,
                evidence_ids=evidence,
                explanation=(
                    f"Entity directly connected to {len(prior_cases)} previously flagged fraud case(s): "
                    f"{[c.id for c in prior_cases]}."
                ),
                is_alert=True,
            )
            matched_rules.append(rule_match)
            all_evidence_ids.update(evidence)

        # ----------------------------------------------------------------------
        # Aggregate Severity & Final Output
        # ----------------------------------------------------------------------
        alert_rules = [r for r in matched_rules if r.is_alert]
        is_alert = len(alert_rules) > 0

        severity = FraudSeverity.NONE
        if any(r.severity == FraudSeverity.CRITICAL for r in alert_rules):
            severity = FraudSeverity.CRITICAL
        elif any(r.severity == FraudSeverity.HIGH for r in alert_rules):
            severity = FraudSeverity.HIGH
        elif any(r.severity == FraudSeverity.MEDIUM for r in alert_rules):
            severity = FraudSeverity.MEDIUM
        elif any(r.severity == FraudSeverity.LOW for r in alert_rules):
            severity = FraudSeverity.LOW

        reason_codes = [r.reason_code for r in alert_rules]

        # Generate summary
        if is_alert:
            summary = f"Fraud alert raised ({severity.value}): " + "; ".join(
                r.explanation for r in alert_rules
            )
            requires_human_review = True
        else:
            summary = "No anomalous fraud patterns detected. Activity within acceptable parameters."
            requires_human_review = False

        return FraudEvaluationResult(
            case_id=case_id,
            is_alert=is_alert,
            severity=severity,
            reason_codes=reason_codes,
            matched_rules=matched_rules,
            evidence_ids=sorted(all_evidence_ids),
            summary=summary,
            requires_human_review=requires_human_review,
            details={
                "total_vertices": neighborhood.total_nodes,
                "total_edges": neighborhood.total_edges,
                "rules_evaluated": 5,
            },
        )


fraud_rule_engine = DeterministicFraudRuleEngine()
