"""API v1 routers for ResolveX AI."""

from fastapi import APIRouter

from backend.app.api.v1.audit_router import router as audit_router
from backend.app.api.v1.auth_router import router as auth_router
from backend.app.api.v1.cases_router import router as cases_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(audit_router)
