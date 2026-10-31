"""Tests verifying the synthetic seed dataset conforms to canonical domain contracts."""

from backend.app.domain.enums import FundsStatus, PaymentStatus
from scripts.seed_synthetic_scenarios import generate_synthetic_dataset


def test_synthetic_dataset_generates_valid_scenarios() -> None:
    """Verifies that seed data covers required payment and fraud scenarios without error."""
    data = generate_synthetic_dataset()

    assert data["tenant"].id == "tenant_finops_01"
    assert len(data["payments"]) >= 5
    assert len(data["cases"]) >= 2
    assert len(data["graph_vertices"]) >= 7
    assert len(data["graph_edges"]) >= 6

    # Verify debit mismatch scenario
    mismatch_pay = next(p for p in data["payments"] if p.id == "pay_scen_mismatch_004")
    assert mismatch_pay.payment_status == PaymentStatus.FAILED
    assert mismatch_pay.funds_status == FundsStatus.CUSTOMER_REPORTED_DEBIT

    # Verify refund delay scenario
    delayed_ref = data["refunds"][0]
    assert delayed_ref.id == "ref_scen_delay_001"
    assert delayed_ref.amount_minor == 199900
