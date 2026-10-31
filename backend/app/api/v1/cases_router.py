"""Case management API endpoints for ResolveX AI."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.domain.case import Approval, Case
from backend.app.domain.enums import ApprovalDecision, CaseStatus, CaseType, FraudSeverity, UserRole
from backend.app.security.auth import get_current_tenant_context, require_roles
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.case_service import case_service

router = APIRouter(prefix="/cases", tags=["Cases"])


class CreateCaseRequest(BaseModel):
    case_type: CaseType
    title: str = Field(..., min_length=3, max_length=200)
    description: str = ""
    linked_payment_ids: list[str] = Field(default_factory=list)
    priority: FraudSeverity = FraudSeverity.LOW


class UpdateCaseStatusRequest(BaseModel):
    new_status: CaseStatus
    reason: str | None = None


class CreateApprovalRequest(BaseModel):
    action_draft: dict


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalDecision
    reason: str | None = None


@router.post("", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    req: CreateCaseRequest,
    request: Request,
    ctx: TenantContext = Depends(
        require_roles(
            UserRole.CUSTOMER,
            UserRole.SUPPORT_ANALYST,
            UserRole.FRAUD_ANALYST,
            UserRole.SUPERVISOR,
            UserRole.PLATFORM_ADMIN,
        )
    ),
) -> Case:
    """Create a new case in the caller's tenant."""
    correlation_id = getattr(request.state, "correlation_id", None)
    return case_service.create_case(
        ctx=ctx,
        case_type=req.case_type,
        title=req.title,
        description=req.description,
        linked_payment_ids=req.linked_payment_ids,
        priority=req.priority,
        correlation_id=correlation_id,
    )


@router.get("", response_model=list[Case])
def list_cases(
    status: CaseStatus | None = None,
    limit: int = 50,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> list[Case]:
    """List cases for the current tenant."""
    return case_service.list_cases(ctx=ctx, status_filter=status, limit=limit)


@router.get("/{case_id}", response_model=Case)
def get_case_detail(
    case_id: str,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> Case:
    """Get single case detail with strict cross-tenant protection."""
    try:
        return case_service.get_case(ctx, case_id)
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


@router.patch("/{case_id}/status", response_model=Case)
def update_case_status(
    case_id: str,
    req: UpdateCaseStatusRequest,
    request: Request,
    ctx: TenantContext = Depends(
        require_roles(
            UserRole.SUPPORT_ANALYST,
            UserRole.FRAUD_ANALYST,
            UserRole.SUPERVISOR,
            UserRole.PLATFORM_ADMIN,
        )
    ),
) -> Case:
    """Update case status (requires analyst or supervisor role)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    try:
        return case_service.update_case_status(
            ctx=ctx,
            case_id=case_id,
            new_status=req.new_status,
            reason=req.reason,
            correlation_id=correlation_id,
        )
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


@router.post("/{case_id}/approval", response_model=Approval, status_code=status.HTTP_201_CREATED)
def request_approval(
    case_id: str,
    req: CreateApprovalRequest,
    request: Request,
    ctx: TenantContext = Depends(
        require_roles(UserRole.SUPPORT_ANALYST, UserRole.FRAUD_ANALYST, UserRole.SUPERVISOR)
    ),
) -> Approval:
    """Create a draft approval for human review."""
    correlation_id = getattr(request.state, "correlation_id", None)
    try:
        return case_service.create_approval_draft(
            ctx=ctx,
            case_id=case_id,
            action_draft=req.action_draft,
            correlation_id=correlation_id,
        )
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


@router.post("/approvals/{approval_id}/decision", response_model=Approval)
def review_approval(
    approval_id: str,
    req: ApprovalDecisionRequest,
    request: Request,
    ctx: TenantContext = Depends(require_roles(UserRole.SUPERVISOR, UserRole.PLATFORM_ADMIN)),
) -> Approval:
    """Decide on a pending approval (supervisor or admin only)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    try:
        return case_service.decide_approval(
            ctx=ctx,
            approval_id=approval_id,
            decision=req.decision,
            reason=req.reason,
            correlation_id=correlation_id,
        )
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
