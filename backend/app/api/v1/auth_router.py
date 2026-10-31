"""Authentication endpoints for ResolveX AI."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.app.domain.enums import UserRole
from backend.app.security.auth import (
    DEMO_USERS,
    LoginRequest,
    LoginResponse,
    create_access_token,
    get_current_tenant_context,
    verify_password,
)
from backend.app.security.context import TenantContext
from backend.app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


class UserProfileResponse(BaseModel):
    id: str
    tenant_id: str
    role: UserRole
    name: str
    email: str


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request) -> LoginResponse:
    """Authenticate user with email and password and return a signed JWT token."""
    user = DEMO_USERS.get(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Optional tenant verification if tenant_id provided in request
    if req.tenant_id and req.tenant_id != user["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User is not a member of tenant '{req.tenant_id}'",
        )

    token = create_access_token(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
        email=req.email,
    )

    # Record login audit event
    correlation_id = getattr(request.state, "correlation_id", None)
    audit_service.record(
        tenant_id=user["tenant_id"],
        actor_id=user["id"],
        action="USER_LOGIN_SUCCESS",
        resource_type="User",
        resource_id=user["id"],
        details={"email": req.email, "role": user["role"].value},
        correlation_id=correlation_id,
    )

    from datetime import datetime, timedelta, timezone

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=60 * 8)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
        email=req.email,
        expires_at=expires_at,
    )


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> UserProfileResponse:
    """Return the profile of the authenticated caller."""
    # Find user profile
    for email, u in DEMO_USERS.items():
        if u["id"] == ctx.user_id and u["tenant_id"] == ctx.tenant_id:
            return UserProfileResponse(
                id=u["id"],
                tenant_id=u["tenant_id"],
                role=u["role"],
                name=u["name"],
                email=email,
            )

    return UserProfileResponse(
        id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        role=ctx.role,
        name="Unknown User",
        email="unknown@example.com",
    )
