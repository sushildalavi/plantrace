from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.ai.service import QueryRegressionInvestigator, build_query_investigator_service
from app.api.deps import get_db
from app.schemas import QueryInvestigationRequest, QueryInvestigationResponse

router = APIRouter(prefix="/api/ai", tags=["ai"])


def get_investigator_service(request: Request) -> QueryRegressionInvestigator:
    service = getattr(request.app.state, "investigator_service", None)
    if service is None:
        service = build_query_investigator_service()
        request.app.state.investigator_service = service
    return service


@router.post("/query-investigation", response_model=QueryInvestigationResponse)
def investigate_query(
    payload: QueryInvestigationRequest,
    db: Session = Depends(get_db),
    service: QueryRegressionInvestigator = Depends(get_investigator_service),
):
    return service.investigate(db=db, request=payload)
