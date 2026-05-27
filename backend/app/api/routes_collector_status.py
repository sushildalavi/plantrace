from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import CollectorStatus
from app.schemas import CollectorStatusOut

router = APIRouter(prefix="/api/collector", tags=["collector"])


@router.get("/status", response_model=list[CollectorStatusOut])
def get_collector_status(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(CollectorStatus)
        .order_by(CollectorStatus.last_seen_at.desc())
        .limit(limit)
        .all()
    )
    return [CollectorStatusOut.model_validate(r) for r in rows]
