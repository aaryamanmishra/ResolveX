"""Tests for Audit Logging and Provenance.

PRD §6 (FR-021): Log actor, tenant, case, action, timestamp, metadata hash,
and evidence IDs. Cross-tenant access fails closed.
"""

from fastapi.testclient import TestClient

from backend.app.domain.enums import UserRole
from backend.app.main import app
from backend.app.security.auth import create_access_token
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service

client = TestClient(app)


def test_mutations_emit_tamper_evident_audit_records() -> None:
    """Verifies that every mutation emits an audit record with a valid SHA-256 hash."""
    audit_service.clear()
    case_service.clear()

    token = create_access_token(
        user_id="usr_support_01",
        tenant_id="tenant_finops_01",
        role=UserRole.SUPPORT_ANALYST,
        email="support@apex.example.com",
    )

    # 1. Create a case
    res = client.post(
        "/api/v1/cases",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Correlation-ID": "corr_test_12345",
        },
        json={"case_type": "PAYMENT_DISCREPANCY", "title": "Audit verification case"},
    )
    assert res.status_code == 201
    case_id = res.json()["id"]

    # 2. Update case status
    patch_res = client.patch(
        f"/api/v1/cases/{case_id}/status",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Correlation-ID": "corr_test_12345",
        },
        json={"new_status": "ESCALATED", "reason": "Requires high tier review"},
    )
    assert patch_res.status_code == 200

    # 3. Query audit events for tenant
    events = audit_service.list_events_for_tenant("tenant_finops_01")
    assert len(events) >= 2

    # Check case created event
    created_event = next(e for e in events if e.action == "CASE_CREATED")
    assert created_event.resource_id == case_id
    assert created_event.actor_id == "usr_support_01"
    assert created_event.tenant_id == "tenant_finops_01"
    assert len(created_event.metadata_hash) == 64  # SHA-256 hash length
    assert created_event.details["correlation_id"] == "corr_test_12345"

    # Check status updated event
    status_event = next(e for e in events if e.action == "CASE_STATUS_UPDATED")
    assert status_event.details["new_status"] == "ESCALATED"
    assert status_event.details["old_status"] == "NEW"


def test_audit_log_endpoint_rbac_and_tenant_isolation() -> None:
    """Audit logs are accessible only to authorized roles and isolated by tenant."""
    audit_service.clear()

    # Seed events for Tenant A and Tenant B
    audit_service.record(
        tenant_id="tenant_a",
        actor_id="usr_a",
        action="TEST_ACTION_A",
        resource_type="Test",
        resource_id="res_a",
    )
    audit_service.record(
        tenant_id="tenant_b",
        actor_id="usr_b",
        action="TEST_ACTION_B",
        resource_type="Test",
        resource_id="res_b",
    )

    # Customer role is forbidden from viewing audit logs
    cust_token = create_access_token(
        user_id="usr_c",
        tenant_id="tenant_a",
        role=UserRole.CUSTOMER,
        email="cust@tenant-a.com",
    )
    cust_res = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert cust_res.status_code == 403

    # Supervisor role in Tenant A can view Tenant A audit logs
    sup_token_a = create_access_token(
        user_id="usr_sup_a",
        tenant_id="tenant_a",
        role=UserRole.SUPERVISOR,
        email="sup@tenant-a.com",
    )
    sup_res = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {sup_token_a}"},
    )
    assert sup_res.status_code == 200
    events_a = sup_res.json()
    assert len(events_a) == 1
    assert events_a[0]["action"] == "TEST_ACTION_A"
    assert events_a[0]["tenant_id"] == "tenant_a"
