"""Tests for tenant-scoped HMAC tokenization and security isolation."""

import pytest

from backend.app.domain.enums import UserRole
from backend.app.security.context import SecurityError, TenantContext
from backend.app.security.tokenization import Tokenizer


def test_tokenization_is_deterministic_within_tenant() -> None:
    """Same identifier within same tenant yields identical token."""
    tokenizer = Tokenizer()
    tok1 = tokenizer.tokenize("tenant_a", "cust_phone_9988776655", prefix="cust")
    tok2 = tokenizer.tokenize("tenant_a", "cust_phone_9988776655", prefix="cust")
    assert tok1 == tok2
    assert tok1.startswith("cust_")


def test_tokenization_diverges_across_tenants() -> None:
    """Same identifier in different tenants must yield different non-correlatable tokens."""
    tokenizer = Tokenizer()
    tok_tenant_a = tokenizer.tokenize("tenant_a", "cust_phone_9988776655", prefix="cust")
    tok_tenant_b = tokenizer.tokenize("tenant_b", "cust_phone_9988776655", prefix="cust")
    assert tok_tenant_a != tok_tenant_b


def test_tenant_context_fails_closed_on_cross_tenant_access() -> None:
    """PRD §6 (FR-002): Cross-tenant access must fail closed."""
    ctx = TenantContext(tenant_id="tenant_a", user_id="usr_01", role=UserRole.SUPPORT_ANALYST)

    # Accessing own tenant is allowed
    ctx.validate_tenant_access("tenant_a")

    # Accessing another tenant raises SecurityError
    with pytest.raises(SecurityError):
        ctx.validate_tenant_access("tenant_b")


def test_tenant_context_role_enforcement() -> None:
    """Verifies RBAC role permission checks."""
    ctx = TenantContext(tenant_id="tenant_a", user_id="usr_01", role=UserRole.CUSTOMER)

    # Allowed role
    ctx.require_role(UserRole.CUSTOMER, UserRole.SUPPORT_ANALYST)

    # Disallowed role raises SecurityError
    with pytest.raises(SecurityError):
        ctx.require_role(UserRole.FRAUD_ANALYST, UserRole.SUPERVISOR)
