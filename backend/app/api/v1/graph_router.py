"""Graph visualization and fraud evaluation endpoints for ResolveX AI.

PRD §6 (FR-010, FR-011, FR-012):
- Retrieve bounded graph nodes, edges, and provenance.
- Deterministic fraud rule evaluation on case graph context.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from backend.app.domain.enums import UserRole
from backend.app.domain.graph import GraphNeighborhood
from backend.app.policies.fraud_rules import FraudEvaluationResult, fraud_rule_engine
from backend.app.security.auth import get_current_tenant_context, require_roles
from backend.app.security.context import SecurityError, TenantContext
from backend.app.services.audit_service import audit_service
from backend.app.services.case_service import case_service
from backend.app.services.graph_service import graph_service

router = APIRouter(tags=["Graph & Fraud Investigation"])


class FraudEvaluationResponse(BaseModel):
    case_id: str
    is_alert: bool
    severity: str
    reason_codes: list[str]
    summary: str
    requires_human_review: bool
    evidence_ids: list[str]
    matched_rules: list[dict]


@router.get("/graph/neighborhood/{entity_token}", response_model=GraphNeighborhood)
def get_entity_neighborhood(
    entity_token: str,
    depth: int = Query(default=2, ge=1, le=4),
    limit: int = Query(default=50, ge=1, le=100),
    ctx: TenantContext = Depends(
        require_roles(
            UserRole.SUPPORT_ANALYST,
            UserRole.FRAUD_ANALYST,
            UserRole.SUPERVISOR,
            UserRole.PLATFORM_ADMIN,
        )
    ),
) -> GraphNeighborhood:
    """Retrieve bounded graph neighborhood around an entity token within caller's tenant."""
    return graph_service.query_neighborhood(
        ctx=ctx,
        entity_token=entity_token,
        depth=depth,
        limit=limit,
    )


@router.get("/cases/{case_id}/graph", response_model=GraphNeighborhood)
def get_case_graph(
    case_id: str,
    depth: int = Query(default=2, ge=1, le=4),
    limit: int = Query(default=50, ge=1, le=100),
    ctx: TenantContext = Depends(get_current_tenant_context),
) -> GraphNeighborhood:
    """Retrieve graph visualization nodes and edges associated with a case."""
    try:
        case = case_service.get_case(ctx, case_id)
    except SecurityError as sec_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(sec_err)) from sec_err
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    # Center search around linked payments or case ID
    center_token = case.linked_payment_ids[0] if case.linked_payment_ids else case.id
    return graph_service.query_neighborhood(
        ctx=ctx,
        entity_token=center_token,
        depth=depth,
        limit=limit,
    )


@router.post("/cases/{case_id}/evaluate-fraud", response_model=FraudEvaluationResponse)
def evaluate_case_fraud_rules(
    case_id: str,
    request: Request,
    depth: int = Query(default=2, ge=1, le=4),
    ctx: TenantContext = Depends(
        require_roles(UserRole.FRAUD_ANALYST, UserRole.SUPERVISOR, UserRole.PLATFORM_ADMIN)
    ),
) -> FraudEvaluationResponse:
    """Run deterministic fraud rules over a case graph neighborhood."""
    try:
        case = case_service.get_case(ctx, case_id)
    except SecurityError as sec_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(sec_err)) from sec_err
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    center_token = case.linked_payment_ids[0] if case.linked_payment_ids else case.id
    neighborhood = graph_service.query_neighborhood(ctx=ctx, entity_token=center_token, depth=depth)

    # Evaluate deterministic policy engine
    result: FraudEvaluationResult = fraud_rule_engine.evaluate_neighborhood(
        case_id=case_id,
        neighborhood=neighborhood,
    )

    # Update case priority if elevated risk detected
    correlation_id = getattr(request.state, "correlation_id", None)
    if result.is_alert and result.severity.value != case.priority.value:
        case_service.update_case_status(
            ctx=ctx,
            case_id=case_id,
            new_status=case.case_status,
            reason=f"Priority updated to {result.severity.value} from fraud rule matches",
            correlation_id=correlation_id,
        )

    audit_service.record(
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action="FRAUD_RULES_EVALUATED",
        resource_type="Case",
        resource_id=case_id,
        details={
            "is_alert": result.is_alert,
            "severity": result.severity.value,
            "reason_codes": result.reason_codes,
            "matched_rules_count": len(result.matched_rules),
        },
        correlation_id=correlation_id,
    )

    return FraudEvaluationResponse(
        case_id=result.case_id,
        is_alert=result.is_alert,
        severity=result.severity.value,
        reason_codes=result.reason_codes,
        summary=result.summary,
        requires_human_review=result.requires_human_review,
        evidence_ids=result.evidence_ids,
        matched_rules=[
            {
                "rule_name": r.rule_name,
                "reason_code": r.reason_code,
                "severity": r.severity.value,
                "explanation": r.explanation,
                "evidence_ids": list(r.evidence_ids),
            }
            for r in result.matched_rules
        ],
    )
