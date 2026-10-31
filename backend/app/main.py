"""ResolveX AI — Main FastAPI Application Entrypoint.

Provides API routes, health checks, OpenAPI specifications, and integration endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.middleware import CorrelationIdMiddleware
from backend.app.api.v1 import api_v1_router
from backend.app.config import settings
from backend.app.graph.graph_store import MemoryGraphStore
from backend.app.providers.model_provider import StubModelProvider
from backend.app.providers.payment_provider import SimulatorPaymentProvider
from backend.app.services.seed_service import seed_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler: seed demo data in demo mode."""
    if settings.DEMO_MODE:
        seed_demo_data()
    yield


app = FastAPI(
    title="ResolveX AI",
    description="Agentic Payment Intelligence, Fraud Investigation & Resolution Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)

# Phase 0 default providers (Demo / Stub Mode)
payment_provider = SimulatorPaymentProvider()
model_provider = StubModelProvider()
graph_store = MemoryGraphStore()


@app.get("/health", tags=["System"])
def health_check() -> dict:
    """System health check and configuration summary."""
    return {
        "status": "HEALTHY",
        "service": "resolvex-api",
        "demo_mode": settings.DEMO_MODE,
        "payment_provider": settings.PAYMENT_PROVIDER,
        "model_provider": settings.MODEL_PROVIDER,
        "graph_engine": settings.GRAPH_ENGINE,
    }


@app.get("/api/v1/admin/model-health", tags=["Admin"])
def get_model_health() -> dict:
    """Model adapter health and capability inspection."""
    health = model_provider.health_check()
    return {
        "status": health.status,
        "provider": health.provider,
        "model_id": health.model_id,
        "capabilities": list(health.capabilities),
        "latency_ms": health.latency_ms,
        "details": health.details,
    }


@app.get("/api/v1/admin/graph-health", tags=["Admin"])
def get_graph_health() -> dict:
    """Graph store adapter health check."""
    health = graph_store.health_check()
    return {
        "status": health.status,
        "engine": health.engine,
        "node_count": health.node_count,
        "edge_count": health.edge_count,
        "details": health.details,
    }


@app.post("/api/v1/admin/seed-demo", tags=["Admin"])
def seed_demo_endpoint() -> dict:
    """Manually trigger synthetic demo seed data."""
    return seed_demo_data()
