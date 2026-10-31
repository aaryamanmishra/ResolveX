"""Tenant-scoped HMAC tokenization utility for ResolveX AI.

PRD §7.3 & §13.1: Tokenize identifiers (customer phone/email, card tokens,
device IDs, UPI references, IP addresses) with a tenant-specific keyed HMAC
before insertion into the graph store or logging.
"""

import hashlib
import hmac


class Tokenizer:
    """Provides deterministic, tenant-isolated HMAC token generation."""

    def __init__(
        self, master_secret: str = "resolvex-default-dev-secret-key-change-in-prod"
    ) -> None:
        self._master_secret = master_secret.encode("utf-8")

    def _derive_tenant_key(self, tenant_id: str) -> bytes:
        """Derive a per-tenant cryptographic subkey using HKDF-like HMAC."""
        return hmac.new(self._master_secret, tenant_id.encode("utf-8"), hashlib.sha256).digest()

    def tokenize(self, tenant_id: str, raw_value: str, prefix: str = "tok") -> str:
        """Deterministically tokenize a sensitive identifier scoped to a tenant.

        Different tenants tokenizing the identical phone number will receive
        different non-correlatable tokens.
        """
        if not raw_value:
            raise ValueError("raw_value cannot be empty")
        if not tenant_id:
            raise ValueError("tenant_id is required for scoped tokenization")

        tenant_key = self._derive_tenant_key(tenant_id)
        token_hash = hmac.new(
            tenant_key, raw_value.strip().encode("utf-8"), hashlib.sha256
        ).hexdigest()[:24]

        return f"{prefix}_{token_hash}"

    def hash_payload(self, raw_bytes: bytes) -> str:
        """Generate SHA-256 hash of raw webhook payload or file bytes."""
        return hashlib.sha256(raw_bytes).hexdigest()
