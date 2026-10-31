"""Tenant-scoped SQL repository for ResolveX AI.

PRD §6 (FR-002): Enforces tenant isolation in database queries, not only UI filters.
Cross-tenant access fails closed by raising SecurityError.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.base import Base
from backend.app.security.context import SecurityError, TenantContext

T = TypeVar("T", bound=Base)


class TenantScopedRepository(Generic[T]):
    """Generic repository enforcing strict tenant isolation on database models."""

    def __init__(self, model_class: type[T], session: AsyncSession) -> None:
        self.model_class = model_class
        self.session = session

    async def create(self, ctx: TenantContext, instance: T) -> T:
        """Persist a new entity tagged with caller's tenant_id."""
        if hasattr(instance, "tenant_id"):
            instance.tenant_id = ctx.tenant_id
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get_by_id(self, ctx: TenantContext, entity_id: str) -> T:
        """Retrieve an entity by ID, guaranteeing tenant boundary."""
        stmt = select(self.model_class).where(self.model_class.id == entity_id)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance is None:
            raise KeyError(f"{self.model_class.__name__} '{entity_id}' not found")

        # Strict tenant boundary check: fail closed if belonging to another tenant
        if hasattr(instance, "tenant_id") and instance.tenant_id != ctx.tenant_id:
            raise SecurityError(
                f"Cross-tenant access violation: Caller tenant '{ctx.tenant_id}' cannot access {self.model_class.__name__} belonging to tenant '{instance.tenant_id}'"
            )

        return instance

    async def list_for_tenant(
        self,
        ctx: TenantContext,
        *filters: Any,
        limit: int = 100,
        offset: int = 0,
    ) -> list[T]:
        """List entities strictly scoped to the caller's tenant."""
        stmt = (
            select(self.model_class)
            .where(
                self.model_class.tenant_id == ctx.tenant_id,  # type: ignore[attr-defined]
                *filters,
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
