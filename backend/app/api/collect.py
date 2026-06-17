from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.collector import run_collection
from app.schemas import CollectResult

router = APIRouter(prefix="/api/collect", tags=["collect"])


@router.post("/run", response_model=CollectResult)
def collect_run(db: Session = Depends(get_db)):
    result = run_collection(db)
    return CollectResult(**result)
