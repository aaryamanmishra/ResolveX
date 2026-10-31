"""Authentication, JWT tokens, and RBAC security services for ResolveX AI.

PRD §6 (FR-001 & FR-002): Server-side authentication and role-based access control.
Enforces tenant isolation across API endpoints.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.domain.enums import UserRole
from backend.app.security.context import SecurityError, TenantContext

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours


class TokenPayload(BaseModel):
    sub: str  # user_id
    tenant_id: str
    role: UserRole
    email: str
    exp: datetime


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_id: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: UserRole
    email: str
    expires_at: datetime


# Pre-seeded demo user database (for demo mode / testing)
DEMO_USERS: dict[str, dict[str, Any]] = {
    "admin@apex.example.com": {
        "id": "usr_admin_01",
        "tenant_id": "tenant_finops_01",
        "role": UserRole.PLATFORM_ADMIN,
        "name": "System Administrator",
        # bcrypt hash for "password123"
        "password_hash": bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8"),
    },
    "supervisor@apex.example.com": {
        "id": "usr_supervisor_01",
        "tenant_id": "tenant_finops_01",
        "role": UserRole.SUPERVISOR,
        "name": "Priya Nair",
        "password_hash": bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8"),
    },
    "fraud.analyst@apex.example.com": {
        "id": "usr_fraud_01",
        "tenant_id": "tenant_finops_01",
        "role": UserRole.FRAUD_ANALYST,
        "name": "Vikram Sethi",
        "password_hash": bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8"),
    },
    "support@apex.example.com": {
        "id": "usr_support_01",
        "tenant_id": "tenant_finops_01",
        "role": UserRole.SUPPORT_ANALYST,
        "name": "Ananya Sharma",
        "password_hash": bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8"),
    },
    "customer@apex.example.com": {
        "id": "usr_cust_01",
        "tenant_id": "tenant_finops_01",
        "role": UserRole.CUSTOMER,
        "name": "Rahul Verma",
        "password_hash": bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8"),
    },
    # Cross-tenant actor for tenant isolation test verification
    "attacker@other.example.com": {
        "id": "usr_other_99",
        "tenant_id": "tenant_other_99",
        "role": UserRole.SUPPORT_ANALYST,
        "name": "Other Tenant User",
        "password_hash": bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8"),
    },
}


def hash_password(password: str) -> str:
    """Generate bcrypt password hash."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: UserRole,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create signed HS256 JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role.value,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate signed JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(
            sub=payload["sub"],
            tenant_id=payload["tenant_id"],
            role=UserRole(payload["role"]),
            email=payload["email"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_tenant_context(
    authorization: str | None = Header(default=None, description="Bearer JWT token"),
) -> TenantContext:
    """FastAPI dependency that extracts and validates the tenant context from the Bearer token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    return TenantContext(
        tenant_id=payload.tenant_id,
        user_id=payload.sub,
        role=payload.role,
        is_system=False,
    )


def require_roles(*allowed_roles: UserRole):
    """Factory creating a FastAPI dependency that enforces role requirements."""

    def role_checker(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        try:
            ctx.require_role(*allowed_roles)
            return ctx
        except SecurityError as err:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(err),
            ) from err

    return role_checker
