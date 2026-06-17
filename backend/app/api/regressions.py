from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.recommendations import recommend_for_query
from app.models import QueryFingerprint, QueryMetric, QueryPlan, QueryRegression
from app.schemas import Page, RecommendationList, RecommendationOut, RegressionListItem, RegressionOut

router = APIRouter(prefix="/api/regressions", tags=["regressions"])


@router.get("", response_model=Page[RegressionListItem])
def list_regressions(
    severity: Literal["critical", "high", "medium", "low", "all"] = "all",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    base = (
        db.query(QueryRegression, QueryFingerprint.normalized_query)
        .join(QueryFingerprint, QueryRegression.fingerprint_id == QueryFingerprint.id)
        .order_by(QueryRegression.created_at.desc())
    )
    if severity != "all":
        base = base.filter(QueryRegression.severity == severity)

    total = base.count()
    rows = base.offset(offset).limit(limit).all()

    items = [
        RegressionListItem(
            id=r.id,
            fingerprint_id=r.fingerprint_id,
            severity=r.severity,
            regression_type=r.regression_type,
            message=r.message,
            old_metric_json=r.old_metric_json,
            new_metric_json=r.new_metric_json,
            created_at=r.created_at,
            normalized_query=nq,
        )
        for r, nq in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{rid}", response_model=RegressionOut)
def get_regression(rid: UUID, db: Session = Depends(get_db)):
    r = db.query(QueryRegression).filter_by(id=str(rid)).first()
    if not r:
        raise HTTPException(status_code=404, detail="regression not found")
    return RegressionOut.model_validate(r)


@router.get("/{rid}/recommendations", response_model=RecommendationList)
def get_regression_recommendations(rid: UUID, db: Session = Depends(get_db)):
    r = db.query(QueryRegression).filter_by(id=str(rid)).first()
    if not r:
        raise HTTPException(status_code=404, detail="regression not found")

    fp = db.query(QueryFingerprint).filter_by(id=r.fingerprint_id).first()
    if not fp:
        raise HTTPException(status_code=404, detail="query not found")

    metric = (
        db.query(QueryMetric)
        .filter_by(fingerprint_id=r.fingerprint_id)
        .order_by(QueryMetric.captured_at.desc())
        .first()
    )
    plan = (
        db.query(QueryPlan)
        .filter_by(fingerprint_id=r.fingerprint_id)
        .order_by(QueryPlan.captured_at.desc())
        .first()
    )

    items = recommend_for_query(
        normalized_query=fp.normalized_query,
        latest_metric=metric,
        latest_plan=plan,
        regression_type=r.regression_type,
    )
    return RecommendationList(items=[RecommendationOut.model_validate(item.to_dict()) for item in items])
