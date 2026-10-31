"""Tests for Tenant Isolation and Cross-Tenant Protection.

PRD §6 (FR-002): Every case, payment, event, evidence object, and audit record
is scoped to a tenant; cross-tenant tests must fail closed.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.domain.enums import UserRole
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.db_models import CaseModel
from backend.app.models.repository import TenantScopedRepository
from backend.app.security.auth import create_access_token
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.case_service import case_service

client = TestClient(app)


def test_cross_tenant_case_access_fails_closed() -> None:
    """A user from Tenant B cannot access or view a case belonging to Tenant A."""
    case_service.clear()

    # 1. Tenant A analyst creates a case in tenant_a
    token_tenant_a = create_access_token(
        user_id="usr_a_01",
        tenant_id="tenant_a",
        role=UserRole.SUPPORT_ANALYST,
        email="analyst@tenant-a.example.com",
    )
    create_res = client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token_tenant_a}"},
        json={
            "case_type": "PAYMENT_DISCREPANCY",
            "title": "Confidential Tenant A Payment Dispute",
            "priority": "HIGH",
        },
    )
    assert create_res.status_code == 201
    case_id_a = create_res.json()["id"]

    # 2. Tenant A analyst can view own case
    view_res_a = client.get(
        f"/api/v1/cases/{case_id_a}",
        headers={"Authorization": f"Bearer {token_tenant_a}"},
    )
    assert view_res_a.status_code == 200

    # 3. Tenant B analyst attempts to view Tenant A's case -> Must fail closed with 403 Forbidden
    token_tenant_b = create_access_token(
        user_id="usr_b_01",
        tenant_id="tenant_b",
        role=UserRole.SUPPORT_ANALYST,
        email="analyst@tenant-b.example.com",
    )
    view_res_b = client.get(
        f"/api/v1/cases/{case_id_a}",
        headers={"Authorization": f"Bearer {token_tenant_b}"},
    )
    assert view_res_b.status_code == 403
    assert "Cross-tenant access forbidden" in view_res_b.json()["detail"]


def test_case_listing_is_strictly_tenant_scoped() -> None:
    """Listing cases only returns records within the caller's tenant boundary."""
    case_service.clear()

    token_tenant_a = create_access_token(
        user_id="usr_a_01",
        tenant_id="tenant_a",
        role=UserRole.SUPPORT_ANALYST,
        email="analyst@tenant-a.example.com",
    )
    token_tenant_b = create_access_token(
        user_id="usr_b_01",
        tenant_id="tenant_b",
        role=UserRole.SUPPORT_ANALYST,
        email="analyst@tenant-b.example.com",
    )

    # Create 2 cases in Tenant A
    client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token_tenant_a}"},
        json={"case_type": "PAYMENT_DISCREPANCY", "title": "Case A-1"},
    )
    client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token_tenant_a}"},
        json={"case_type": "PAYMENT_DISCREPANCY", "title": "Case A-2"},
    )

    # Create 1 case in Tenant B
    client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token_tenant_b}"},
        json={"case_type": "PAYMENT_DISCREPANCY", "title": "Case B-1"},
    )

    # List cases as Tenant A
    list_a = client.get(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token_tenant_a}"},
    ).json()
    assert len(list_a) == 2
    assert all(c["tenant_id"] == "tenant_a" for c in list_a)

    # List cases as Tenant B
    list_b = client.get(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token_tenant_b}"},
    ).json()
    assert len(list_b) == 1
    assert list_b[0]["title"] == "Case B-1"
    assert list_b[0]["tenant_id"] == "tenant_b"


@pytest.mark.asyncio
async def test_database_repository_tenant_scoping() -> None:
    """Repository layer strictly validates tenant boundary and fails closed."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    ctx_a = TenantContext(tenant_id="tenant_a", user_id="usr_a", role=UserRole.SUPPORT_ANALYST)
    ctx_b = TenantContext(tenant_id="tenant_b", user_id="usr_b", role=UserRole.SUPPORT_ANALYST)

    async with session_maker() as session:
        repo = TenantScopedRepository(CaseModel, session)

        # Create case in Tenant A
        case_a = CaseModel(
            id="db_case_001",
            tenant_id="tenant_a",
            case_type="PAYMENT_DISCREPANCY",
            title="Database Case for Tenant A",
        )
        await repo.create(ctx_a, case_a)
        await session.commit()

        # Querying with Tenant A succeeds
        found = await repo.get_by_id(ctx_a, "db_case_001")
        assert found.id == "db_case_001"
        assert found.tenant_id == "tenant_a"

        # Querying with Tenant B must raise SecurityError
        with pytest.raises(SecurityError):
            await repo.get_by_id(ctx_b, "db_case_001")

        # Listing for Tenant B returns empty
        cases_b = await repo.list_for_tenant(ctx_b)
        assert len(cases_b) == 0

    await engine.dispose()
