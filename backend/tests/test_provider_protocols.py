"""Tests for payment, model, and graph provider protocols and implementations."""

import json

from backend.app.domain.enums import PaymentStatus
from backend.app.domain.payment import CreatePaymentRequest
from backend.app.graph.graph_store import GraphStore, MemoryGraphStore
from backend.app.providers.model_provider import (
    ModelProvider,
    ModelRequest,
    StubModelProvider,
)
from backend.app.providers.payment_provider import (
    PaymentProviderAdapter,
    SimulatorPaymentProvider,
)


def test_payment_provider_adapter_compliance() -> None:
    """SimulatorPaymentProvider must fulfill the PaymentProviderAdapter protocol."""
    sim = SimulatorPaymentProvider()
    assert isinstance(sim, PaymentProviderAdapter)
    assert sim.provider_name == "simulator"

    # Test payment creation
    req = CreatePaymentRequest(
        tenant_id="t1",
        merchant_id="m1",
        order_ref="ORD-TEST",
        amount_minor=25000,
        currency="INR",
        customer_token="cust_test",
    )
    result = sim.create_payment(req)
    assert result.amount_minor == 25000
    assert result.normalized_status == PaymentStatus.CREATED

    # Test status lookup
    queried = sim.get_payment_status(result.provider_payment_id)
    assert queried.provider_payment_id == result.provider_payment_id


def test_simulator_webhook_signature_verification() -> None:
    """Simulator must sign and verify webhook signatures correctly."""
    sim = SimulatorPaymentProvider()
    body = json.dumps({"event_id": "evt_1", "status": "succeeded", "amount_minor": 1000}).encode(
        "utf-8"
    )
    sig = sim.generate_signature(body)

    # Valid signature
    assert sim.verify_webhook_signature(body, {"X-Simulator-Signature": sig}) is True

    # Tampered body fails signature check
    tampered = json.dumps({"event_id": "evt_1", "status": "failed", "amount_minor": 1000}).encode(
        "utf-8"
    )
    assert sim.verify_webhook_signature(tampered, {"X-Simulator-Signature": sig}) is False

    # Missing header fails
    assert sim.verify_webhook_signature(body, {}) is False


def test_model_provider_compliance() -> None:
    """StubModelProvider must fulfill the ModelProvider protocol and health check."""
    stub = StubModelProvider()
    assert isinstance(stub, ModelProvider)
    assert stub.provider_name == "stub"

    health = stub.health_check()
    assert health.status == "HEALTHY"
    assert "text" in health.capabilities
    assert "image" in health.capabilities

    # Test multimodal extraction
    img_result = stub.analyze_image(
        ModelRequest(prompt="Extract receipt details"),
        image_bytes=b"fake_image_bytes",
        mime_type="image/png",
    )
    assert len(img_result.claims) >= 1
    assert img_result.claims[0].field_name == "amount_minor"


def test_graph_store_compliance() -> None:
    """MemoryGraphStore must fulfill the GraphStore protocol."""
    store = MemoryGraphStore()
    assert isinstance(store, GraphStore)
    assert store.engine_name == "memory"
    health = store.health_check()
    assert health.status == "HEALTHY"
