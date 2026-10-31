"""Case management and Agent Investigation API endpoints for ResolveX AI.

PRD §11:
- POST /api/v1/cases: Create a case
- GET  /api/v1/cases: List cases
- GET  /api/v1/cases/{case_id}: Case detail
- PATCH /api/v1/cases/{case_id}/status: Transition case status
- POST /api/v1/cases/{case_id}/investigate: Start bounded LangGraph investigation
- GET  /api/v1/cases/{case_id}/findings: Retrieve canonical investigation findings
- POST /api/v1/cases/{case_id}/approval: Draft action approval request
- POST /api/v1/cases/approvals/{approval_id}/decision: Human reviewer approval sign-off
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.agents.workflow import investigation_runner
from backend.app.domain.case import Approval, Case
from backend.app.domain.enums import ApprovalDecision, CaseStatus, CaseType, FraudSeverity, UserRole
from backend.app.domain.findings import StructuredInvestigationResult
from backend.app.security.auth import get_current_tenant_context, require_roles
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.case_service import case_service

router = APIRouter(prefix="/cases", tags=["Cases"])


class InvestigateCaseRequest(BaseModel):
    track: Literal["payment_issue", "fraud_investigation"] = "payment_issue"


class InvestigateCaseResponse(BaseModel):
    case_id: str
    run_id: str
    execution_status: str
    requires_human_approval: bool
    approval_id: str | None = None
    step_count: int
    findings_count: int
    latency_ms: int
    summary: str
    structured_result: StructuredInvestigationResult | None = None


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


@router.post("/{case_id}/investigate", response_model=InvestigateCaseResponse)
def investigate_case(
    case_id: str,
    req: InvestigateCaseRequest,
    ctx: TenantContext = Depends(
        require_roles(
            UserRole.SUPPORT_ANALYST,
            UserRole.FRAUD_ANALYST,
            UserRole.SUPERVISOR,
            UserRole.PLATFORM_ADMIN,
        )
    ),
) -> InvestigateCaseResponse:
    """Run bounded LangGraph investigation workflow for the case."""
    try:
        final_state = investigation_runner.run_investigation(
            ctx=ctx,
            case_id=case_id,
            track=req.track,
        )
        res_obj = (
            StructuredInvestigationResult.model_validate(final_state["structured_result"])
            if final_state.get("structured_result")
            else None
        )

        return InvestigateCaseResponse(
            case_id=case_id,
            run_id=final_state.get("run_id", "unknown_run"),
            execution_status=final_state.get("execution_status", "UNKNOWN"),
            requires_human_approval=final_state.get("requires_human_approval", False),
            approval_id=final_state.get("approval_id"),
            step_count=final_state.get("step_count", 0),
            findings_count=len(final_state.get("validated_findings", [])),
            latency_ms=final_state.get("latency_ms", 0),
            summary=final_state.get("synthesis_summary", "Investigation run complete."),
            structured_result=res_obj,
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


@router.get("/{case_id}/findings", response_model=StructuredInvestigationResult)
def get_case_findings(
    case_id: str,
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> StructuredInvestigationResult:
    """Retrieve canonical structured investigation result for a case."""
    try:
        case_service.get_case(ctx, case_id)
        findings = investigation_runner.get_latest_findings(ctx, case_id)
        if not findings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No investigation findings recorded for case '{case_id}'. Run /investigate first.",
            )
        return findings
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
        # Check if an active paused investigation is waiting on this approval
        # Find which case this approval belongs to
        approval = case_service.decide_approval(
            ctx=ctx,
            approval_id=approval_id,
            decision=req.decision,
            reason=req.reason,
            correlation_id=correlation_id,
        )
        # Attempt to resume workflow runner if paused
        try:
            investigation_runner.resume_with_approval(
                ctx=ctx,
                case_id=approval.case_id,
                approval_id=approval_id,
                decision=req.decision,
                reason=req.reason,
            )
        except Exception:
            pass  # If no active paused graph thread was active, the decision is still cleanly saved
        return approval
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
