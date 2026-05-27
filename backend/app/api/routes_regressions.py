from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import QueryFingerprint, QueryRegression
from app.schemas import Page, RegressionListItem, RegressionOut

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
