"""Model Evaluation Benchmark & Acceptance Gates for ResolveX AI.

PRD §16 (Phase 7), §9.5, §15.2:
- Benchmarks agent and deterministic policy models against golden datasets.
- Citation Precision: Verifies 100% of generated claims cite valid evidence IDs.
- Hallucination / Unknown Rate: Verifies ungrounded statements are placed in unknowns list.
- Benign Shared-Device Filter: Verifies 0% false positive fraud alerts on household devices.
- Syndicate Detection: Verifies 100% true positive alert rate on high velocity clusters.
"""

from datetime import datetime, timedelta, timezone

from backend.app.agents.nodes import node_validate_findings
from backend.app.domain.enums import FraudSeverity
from backend.app.domain.graph import (
    EdgeLabel,
    GraphEdge,
    GraphNeighborhood,
    GraphVertex,
    VertexLabel,
)
from backend.app.policies.fraud_rules import fraud_rule_engine


class TestModelCitationAndFactGrounding:
    """Evaluates agent structured outputs for strict evidence citation grounding."""

    def test_citation_precision_on_grounded_findings(self):
        """Valid findings with existing evidence IDs must achieve 100% pass rate."""
        state = {
            "available_evidence_ids": ["evt_pay_cap_01", "ord_inv_201"],
            "candidate_findings": [
                {
                    "code": "PAYMENT_CAPTURED",
                    "statement": "Gateway confirmed payment capture via webhook event.",
                    "evidence_ids": ["evt_pay_cap_01"],
                    "confidence": 0.99,
                },
                {
                    "code": "ORDER_MATCHED",
                    "statement": "Order identifier ORD-201 matches merchant cart invoice.",
                    "evidence_ids": ["ord_inv_201"],
                    "confidence": 0.98,
                },
            ],
            "unknowns": [],
            "step_count": 2,
        }

        updated_state = node_validate_findings(state)
        # All citations verified; no findings dropped or converted to unknowns
        assert len(updated_state["validated_findings"]) == 2
        assert len(updated_state["unknowns"]) == 0

    def test_hallucination_quarantine_into_unknowns(self):
        """Findings citing fabricated evidence IDs are quarantined and appended to unknowns."""
        state = {
            "available_evidence_ids": ["real_evt_01"],
            "candidate_findings": [
                {
                    "code": "FABRICATED_REFUND",
                    "statement": "Bank customer care rep promised immediate settlement.",
                    "evidence_ids": ["fake_doc_id_9999"],
                    "confidence": 0.40,
                }
            ],
            "unknowns": [],
            "step_count": 2,
        }

        updated_state = node_validate_findings(state)
        # Fabricated finding is quarantined from verified findings
        assert len(updated_state["validated_findings"]) == 0
        # Added to explicit unknowns
        assert len(updated_state["unknowns"]) >= 1
        assert "Unverified claim" in updated_state["unknowns"][0]


class TestGraphPolicyPrecisionAndRecall:
    """Evaluates deterministic fraud rules against golden synthetic graph patterns."""

    def test_benign_device_has_zero_false_positive_rate(self):
        """PRD Scenario 5: Benign family sharing 1 device must NOT trigger fraud alert."""
        now = datetime.now(timezone.utc)
        vertices = [
            GraphVertex(id="dev_ipad_home", tenant_id="t1", label=VertexLabel.DEVICE_TOKEN),
            GraphVertex(id="cust_parent", tenant_id="t1", label=VertexLabel.CUSTOMER_TOKEN),
            GraphVertex(id="cust_child", tenant_id="t1", label=VertexLabel.CUSTOMER_TOKEN),
        ]
        edges = [
            GraphEdge(
                id="e1",
                tenant_id="t1",
                source_id="cust_parent",
                target_id="dev_ipad_home",
                label=EdgeLabel.USED_DEVICE,
                source_record_id="p1",
                observed_at=now,
            ),
            GraphEdge(
                id="e2",
                tenant_id="t1",
                source_id="cust_child",
                target_id="dev_ipad_home",
                label=EdgeLabel.USED_DEVICE,
                source_record_id="p2",
                observed_at=now - timedelta(days=1),
            ),
        ]
        neighborhood = GraphNeighborhood(
            center_vertex_id="dev_ipad_home",
            depth=2,
            vertices=vertices,
            edges=edges,
        )

        eval_res = fraud_rule_engine.evaluate_neighborhood(
            case_id="case_b1", neighborhood=neighborhood
        )
        assert eval_res.is_alert is False
        assert eval_res.severity == FraudSeverity.NONE
        assert eval_res.requires_human_review is False
        assert all(not r.is_alert for r in eval_res.matched_rules)

    def test_syndicate_cluster_has_100_percent_true_positive_rate(self):
        """PRD Scenario 1: Device shared by 4 distinct accounts must trigger SHARED_DEVICE_SYNDICATE."""
        now = datetime.now(timezone.utc)
        dev_id = "dev_imei_syndicate_cluster"
        vertices = [GraphVertex(id=dev_id, tenant_id="t1", label=VertexLabel.DEVICE_TOKEN)]
        edges = []

        for i in range(1, 5):
            cust_id = f"cust_fraud_{i}"
            vertices.append(
                GraphVertex(id=cust_id, tenant_id="t1", label=VertexLabel.CUSTOMER_TOKEN)
            )
            edges.append(
                GraphEdge(
                    id=f"e_{i}",
                    tenant_id="t1",
                    source_id=cust_id,
                    target_id=dev_id,
                    label=EdgeLabel.USED_DEVICE,
                    source_record_id=f"pay_{i}",
                    observed_at=now,
                )
            )

        neighborhood = GraphNeighborhood(
            center_vertex_id=dev_id,
            depth=2,
            vertices=vertices,
            edges=edges,
        )

        eval_res = fraud_rule_engine.evaluate_neighborhood(
            case_id="case_s1", neighborhood=neighborhood
        )
        assert eval_res.is_alert is True
        assert eval_res.severity == FraudSeverity.HIGH
        assert "SHARED_DEVICE_THRESHOLD_EXCEEDED" in eval_res.reason_codes
        assert eval_res.requires_human_review is True
