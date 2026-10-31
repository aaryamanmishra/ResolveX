"""Provider adapters and interfaces for ResolveX AI."""

from backend.app.providers.model_provider import (
    EvidenceExtractionResult,
    ModelProvider,
    ModelRequest,
    ProviderHealth,
    StructuredResult,
    StubModelProvider,
    TextResult,
)
from backend.app.providers.payment_provider import (
    PaymentProviderAdapter,
    SimulatorPaymentProvider,
)
from backend.app.providers.razorpay_provider import RazorpayPaymentProvider

__all__ = [
    "EvidenceExtractionResult",
    "ModelProvider",
    "ModelRequest",
    "PaymentProviderAdapter",
    "ProviderHealth",
    "RazorpayPaymentProvider",
    "SimulatorPaymentProvider",
    "StructuredResult",
    "StubModelProvider",
    "TextResult",
]
