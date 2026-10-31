"""Payment management, webhook ingress, and timeline API endpoints for ResolveX AI.

PRD §6 (FR-003 to FR-008, FR-022) & §11:
- Signed webhook reception with raw body verification.
- Searchable payment list, detail, and timeline.
- Unresolved reconciliation exceptions queue.
- Demo payment simulation endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.app.domain.enums import FundsStatus, PaymentStatus, UserRole
from backend.app.domain.payment import (
    CreatePaymentRequest,
    Payment,
    PaymentEvent,
    Refund,
)
from backend.app.security.auth import get_current_tenant_context, require_roles
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.payment_service import IngestWebhookResult, payment_service
from backend.app.services.reconciliation_service import reconciliation_engine

payments_router = APIRouter(prefix="/payments", tags=["Payments"])
webhooks_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
refunds_router = APIRouter(prefix="/refunds", tags=["Refunds"])


class ReportDebitRequest(BaseModel):
    evidence_id: str | None = None
    note: str | None = None


@payments_router.post("", response_model=Payment, status_code=status.HTTP_201_CREATED)
def create_payment(
    req: CreatePaymentRequest,
    request: Request,
    ctx: TenantContext = Depends(
        require_roles(UserRole.CUSTOMER, UserRole.SUPPORT_ANALYST, UserRole.PLATFORM_ADMIN)
    ),
) -> Payment:
    """Create a new payment order and session."""
    correlation_id = getattr(request.state, "correlation_id", None)
    return payment_service.create_payment(ctx=ctx, request=req, correlation_id=correlation_id)


@payments_router.get("", response_model=list[Payment])
def list_payments(
    payment_status: PaymentStatus | None = None,
    funds_status: FundsStatus | None = None,
    limit: int = 50,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> list[Payment]:
    """List payments strictly scoped to the caller's tenant."""
    return payment_service.list_payments(
        ctx=ctx,
        payment_status=payment_status,
        funds_status=funds_status,
        limit=limit,
    )


@payments_router.get("/exceptions/queue")
def list_reconciliation_exceptions(
    ctx: TenantContext = Depends(
        require_roles(
            UserRole.SUPPORT_ANALYST,
            UserRole.FRAUD_ANALYST,
            UserRole.SUPERVISOR,
            UserRole.PLATFORM_ADMIN,
        )
    ),
) -> list[dict]:
    """Retrieve active reconciliation exceptions and payment discrepancies."""
    exceptions = reconciliation_engine.list_exceptions(ctx.tenant_id)
    return [
        {
            "discrepancy_code": ex.discrepancy_code,
            "payment_id": ex.payment_id,
            "description": ex.description,
            "severity": ex.severity.value,
            "evidence_ids": list(ex.evidence_ids),
            "details": ex.details,
        }
        for ex in exceptions
    ]


@payments_router.get("/{payment_id}", response_model=Payment)
def get_payment(
    payment_id: str,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> Payment:
    """Get authoritative payment record with tenant protection."""
    try:
        return payment_service.get_payment(ctx=ctx, payment_id=payment_id)
    except SecurityError as sec_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(sec_err),
        ) from sec_err
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@payments_router.get("/{payment_id}/timeline", response_model=list[PaymentEvent])
def get_payment_timeline(
    payment_id: str,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> list[PaymentEvent]:
    """Get immutable, append-only timeline of provider and system events."""
    try:
        return payment_service.get_timeline(ctx=ctx, payment_id=payment_id)
    except SecurityError as sec_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(sec_err)) from sec_err
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@payments_router.post("/{payment_id}/report-debit", response_model=Payment)
def report_customer_debit(
    payment_id: str,
    req: ReportDebitRequest,
    request: Request,
    ctx: TenantContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.SUPPORT_ANALYST)),
) -> Payment:
    """Record a customer claim of bank debit without overwriting provider payment truth."""
    correlation_id = getattr(request.state, "correlation_id", None)
    try:
        return payment_service.report_customer_debit(
            ctx=ctx,
            payment_id=payment_id,
            correlation_id=correlation_id,
        )
    except SecurityError as sec_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(sec_err)) from sec_err
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@webhooks_router.post("/{provider}", status_code=status.HTTP_200_OK)
async def receive_provider_webhook(
    provider: str,
    request: Request,
) -> dict:
    """Ingest signed webhook from payment provider (Simulator or Razorpay)."""
    raw_body = await request.body()
    headers = dict(request.headers)
    correlation_id = getattr(request.state, "correlation_id", None)

    try:
        result: IngestWebhookResult = payment_service.ingest_webhook(
            provider_name=provider,
            raw_body=raw_body,
            headers=headers,
            correlation_id=correlation_id,
        )
        return {
            "status": result.status,
            "provider": result.provider,
            "provider_event_id": result.provider_event_id,
            "idempotency_key": result.idempotency_key,
            "is_duplicate": result.is_duplicate,
            "normalized_status": result.normalized_status.value,
            "message": result.message,
        }
    except SecurityError as sec_err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook signature check failed: {sec_err}",
        ) from sec_err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error parsing webhook payload: {err}",
        ) from err


@refunds_router.get("/{refund_id}", response_model=Refund)
def get_refund_status(
    refund_id: str,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> Refund:
    """Fetch refund status with tenant isolation."""
    try:
        return payment_service.get_refund(ctx=ctx, refund_id=refund_id)
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
