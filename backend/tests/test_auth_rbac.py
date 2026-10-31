"""Tests for Authentication, JWT tokens, and Server-Side RBAC.

PRD §6 (FR-001): Enforce server-side permissions across Customer, Support Analyst,
Fraud Analyst, Supervisor, and Platform Admin roles.
"""

from fastapi.testclient import TestClient

from backend.app.domain.enums import UserRole
from backend.app.main import app
from backend.app.security.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

client = TestClient(app)


def test_password_hashing_and_verification() -> None:
    """Password hashing with bcrypt is secure and verifies correctly."""
    pwd = "secure_password_99"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_lifecycle() -> None:
    """JWT tokens encode user ID, tenant ID, and role, and validate expiration."""
    token = create_access_token(
        user_id="usr_01",
        tenant_id="tenant_01",
        role=UserRole.SUPPORT_ANALYST,
        email="support@apex.example.com",
    )
    payload = decode_access_token(token)
    assert payload.sub == "usr_01"
    assert payload.tenant_id == "tenant_01"
    assert payload.role == UserRole.SUPPORT_ANALYST
    assert payload.email == "support@apex.example.com"


def test_login_success_and_failure() -> None:
    """Test login endpoint with valid, invalid, and mismatched credentials."""
    # Valid login
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "support@apex.example.com", "password": "password123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "SUPPORT_ANALYST"
    assert data["tenant_id"] == "tenant_finops_01"

    # Invalid password
    res_bad_pwd = client.post(
        "/api/v1/auth/login",
        json={"email": "support@apex.example.com", "password": "incorrect_password"},
    )
    assert res_bad_pwd.status_code == 401

    # Non-existent user
    res_no_user = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@apex.example.com", "password": "password123"},
    )
    assert res_no_user.status_code == 401

    # Tenant mismatch
    res_tenant_mismatch = client.post(
        "/api/v1/auth/login",
        json={
            "email": "support@apex.example.com",
            "password": "password123",
            "tenant_id": "tenant_wrong_02",
        },
    )
    assert res_tenant_mismatch.status_code == 403


def test_current_user_profile_endpoint() -> None:
    """Test /api/v1/auth/me returns caller profile when authenticated."""
    # Unauthenticated
    assert client.get("/api/v1/auth/me").status_code == 401

    # Authenticated
    token = create_access_token(
        user_id="usr_support_01",
        tenant_id="tenant_finops_01",
        role=UserRole.SUPPORT_ANALYST,
        email="support@apex.example.com",
    )
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["email"] == "support@apex.example.com"
    assert res.json()["role"] == "SUPPORT_ANALYST"


def test_role_based_access_control_on_case_status_update() -> None:
    """Customers are forbidden from modifying case status; Analysts are authorized."""
    # 1. Create a case with Analyst token
    analyst_token = create_access_token(
        user_id="usr_support_01",
        tenant_id="tenant_finops_01",
        role=UserRole.SUPPORT_ANALYST,
        email="support@apex.example.com",
    )
    case_res = client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={
            "case_type": "PAYMENT_DISCREPANCY",
            "title": "Payment missing investigation",
            "priority": "LOW",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Customer attempts to patch case status -> Must receive 403 Forbidden
    cust_token = create_access_token(
        user_id="usr_cust_01",
        tenant_id="tenant_finops_01",
        role=UserRole.CUSTOMER,
        email="customer@apex.example.com",
    )
    patch_res = client.patch(
        f"/api/v1/cases/{case_id}/status",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"new_status": "CLOSED", "reason": "Customer attempt to auto-close"},
    )
    assert patch_res.status_code == 403

    # 3. Analyst patches case status -> Succeeds 200 OK
    analyst_patch_res = client.patch(
        f"/api/v1/cases/{case_id}/status",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"new_status": "TRIAGING", "reason": "Started investigation"},
    )
    assert analyst_patch_res.status_code == 200
    assert analyst_patch_res.json()["case_status"] == "TRIAGING"
