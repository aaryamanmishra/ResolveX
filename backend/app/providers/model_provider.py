"""Model Provider Protocol and Stub Adapter for ResolveX AI.

PRD §9.2 & §12.3: Provider-neutral, capability-aware model interface.
Keeps Gemma 4 (open-weights on DO GPU) and Gemini API (managed multimodal)
fully interchangeable without modifying business logic.

API KEYS REQUIRED IN PRODUCTION:
- GEMINI_API_KEY: Google Gemini API Key (when using Gemini model routes)
- GEMMA_ENDPOINT_URL: URL to deployed Gemma 4 vLLM/custom inference server (DO GPU Droplet)
- GEMMA_AUTH_TOKEN: Bearer token for private Gemma 4 inference server
In demo/development mode, StubModelProvider runs deterministically without paid keys.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from backend.app.domain.evidence import EvidenceClaim
from backend.app.domain.findings import ModelMetadata

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ProviderHealth:
    """Health check status and capabilities of the active model adapter."""

    status: str  # "HEALTHY", "DEGRADED", "UNAVAILABLE"
    provider: str  # "gemma", "gemini", "stub"
    model_id: str
    capabilities: tuple[str, ...]
    latency_ms: int
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TextResult:
    """Raw text completion result."""

    text: str
    model_metadata: ModelMetadata
    token_usage: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuredResult(Generic[T]):
    """Strictly typed structured generation matching a Pydantic schema."""

    parsed: T
    raw_json: str
    model_metadata: ModelMetadata


@dataclass(frozen=True)
class EvidenceExtractionResult:
    """Multimodal claims extracted from an image, document, or audio file."""

    claims: list[EvidenceClaim]
    raw_summary: str
    model_metadata: ModelMetadata


@dataclass(frozen=True)
class ModelRequest:
    """Common request payload for model inference."""

    prompt: str
    system_instruction: str = ""
    temperature: float = 0.0
    max_tokens: int = 2048


@runtime_checkable
class ModelProvider(Protocol):
    """Protocol for interchangeable LLM/multimodal backends."""

    @property
    def provider_name(self) -> str:
        """Name of provider adapter (gemma, gemini, stub)."""
        ...

    def generate_text(self, request: ModelRequest) -> TextResult:
        """Perform text generation."""
        ...

    def generate_structured(
        self, request: ModelRequest, response_model: type[T]
    ) -> StructuredResult[T]:
        """Generate output strictly adhering to a Pydantic response_model."""
        ...

    def analyze_image(
        self, request: ModelRequest, image_bytes: bytes, mime_type: str
    ) -> EvidenceExtractionResult:
        """Extract candidate claims and bounding locations from image."""
        ...

    def analyze_audio(
        self, request: ModelRequest, audio_bytes: bytes, mime_type: str
    ) -> EvidenceExtractionResult:
        """Extract candidate claims and timestamps from audio recording."""
        ...

    def analyze_document(
        self, request: ModelRequest, doc_bytes: bytes, mime_type: str
    ) -> EvidenceExtractionResult:
        """Extract candidate claims from PDF/document."""
        ...

    def health_check(self) -> ProviderHealth:
        """Verify model adapter connectivity and report supported modalities."""
        ...


class StubModelProvider:
    """Deterministic, zero-key model provider for Demo Mode and offline testing.

    Ensures the platform runs end-to-end without requiring paid API keys or active GPUs.
    """

    def __init__(self, model_id: str = "resolvex-stub-v1") -> None:
        self.model_id = model_id

    @property
    def provider_name(self) -> str:
        return "stub"

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            status="HEALTHY",
            provider="stub",
            model_id=self.model_id,
            capabilities=("text", "structured_json", "image", "audio", "document"),
            latency_ms=1,
            details={"demo_mode": True, "api_key_required": False},
        )

    def generate_text(self, request: ModelRequest) -> TextResult:
        return TextResult(
            text="Stub model output: deterministic investigation summary.",
            model_metadata=ModelMetadata(
                provider="stub",
                model_id=self.model_id,
                prompt_version="stub-v1",
                execution_time_ms=1,
            ),
        )

    def generate_structured(
        self, request: ModelRequest, response_model: type[T]
    ) -> StructuredResult[T]:
        """Attempts to construct a minimal valid instance of response_model for tests."""
        # Check if the requested schema has dummy defaults or construct via empty dict
        try:
            instance = response_model.model_validate({})
        except Exception:
            # If empty fails, return dummy json that satisfies the model or let caller handle
            dummy_json = "{}"
            instance = response_model.model_validate_json(dummy_json)

        return StructuredResult(
            parsed=instance,
            raw_json="{}",
            model_metadata=ModelMetadata(
                provider="stub",
                model_id=self.model_id,
                prompt_version="stub-v1",
                execution_time_ms=1,
            ),
        )

    def analyze_image(
        self, request: ModelRequest, image_bytes: bytes, mime_type: str
    ) -> EvidenceExtractionResult:
        now = datetime.now(timezone.utc)
        claims = [
            EvidenceClaim(
                id="claim_stub_img_001",
                evidence_asset_id="evid_stub_img",
                field_name="amount_minor",
                candidate_value="50000",
                confidence=0.98,
                source_location={"box_2d": [100, 200, 150, 400], "page": 1},
                created_at=now,
            ),
            EvidenceClaim(
                id="claim_stub_img_002",
                evidence_asset_id="evid_stub_img",
                field_name="utr",
                candidate_value="UPI428198739182",
                confidence=0.95,
                source_location={"box_2d": [300, 150, 340, 500], "page": 1},
                created_at=now,
            ),
        ]
        return EvidenceExtractionResult(
            claims=claims,
            raw_summary="Extracted amount and UTR from payment receipt screenshot.",
            model_metadata=ModelMetadata(
                provider="stub",
                model_id=self.model_id,
                prompt_version="evidence-intake-v1",
                execution_time_ms=5,
            ),
        )

    def analyze_audio(
        self, request: ModelRequest, audio_bytes: bytes, mime_type: str
    ) -> EvidenceExtractionResult:
        now = datetime.now(timezone.utc)
        claims = [
            EvidenceClaim(
                id="claim_stub_aud_001",
                evidence_asset_id="evid_stub_aud",
                field_name="customer_statement",
                candidate_value="Money was debited from bank account but order showed pending",
                confidence=0.90,
                source_location={"audio_start_sec": 1.2, "audio_end_sec": 6.8},
                created_at=now,
            )
        ]
        return EvidenceExtractionResult(
            claims=claims,
            raw_summary="Transcribed voice note customer claim.",
            model_metadata=ModelMetadata(
                provider="stub",
                model_id=self.model_id,
                prompt_version="evidence-intake-v1",
                execution_time_ms=5,
            ),
        )

    def analyze_document(
        self, request: ModelRequest, doc_bytes: bytes, mime_type: str
    ) -> EvidenceExtractionResult:
        now = datetime.now(timezone.utc)
        claims = [
            EvidenceClaim(
                id="claim_stub_doc_001",
                evidence_asset_id="evid_stub_doc",
                field_name="bank_statement_debit",
                candidate_value="INR 500.00 debited on 2026-10-31",
                confidence=0.92,
                source_location={"page": 1, "line": 14},
                created_at=now,
            )
        ]
        return EvidenceExtractionResult(
            claims=claims,
            raw_summary="Parsed bank statement statement entry.",
            model_metadata=ModelMetadata(
                provider="stub",
                model_id=self.model_id,
                prompt_version="evidence-intake-v1",
                execution_time_ms=5,
            ),
        )
