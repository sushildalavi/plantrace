from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.report_generator import build_findings, render_report
from app.models import QueryFingerprint, QueryMetric, QueryPlan, QueryRegression, QueryReport
from app.schemas import ReportResult

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _get_fp_or_404(fid: str, db: Session) -> QueryFingerprint:
    fp = db.query(QueryFingerprint).filter_by(id=fid).first()
    if not fp:
        raise HTTPException(status_code=404, detail="query not found")
    return fp


@router.post("/{fid}/generate", response_model=ReportResult)
def generate_report(fid: UUID, db: Session = Depends(get_db)):
    fp = _get_fp_or_404(str(fid), db)

    latest_m = (
        db.query(QueryMetric)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryMetric.captured_at.desc())
        .first()
    )
    latest_p = (
        db.query(QueryPlan)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryPlan.captured_at.desc())
        .first()
    )
    recent_regs = (
        db.query(QueryRegression)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryRegression.created_at.desc())
        .limit(5)
        .all()
    )

    findings = build_findings(fp, latest_m, latest_p, recent_regs)
    generated_text, model_name = render_report(findings)

    # upsert: delete old report for this fingerprint, insert new
    db.query(QueryReport).filter_by(fingerprint_id=fp.id).delete()
    report = QueryReport(
        fingerprint_id=fp.id,
        generated_text=generated_text,
        model_name=model_name,
    )
    db.add(report)
    db.commit()

    return ReportResult(generated_text=generated_text, model_name=model_name, findings=findings)


@router.get("/{fid}", response_model=ReportResult)
def get_report(fid: UUID, db: Session = Depends(get_db)):
    _get_fp_or_404(str(fid), db)
    report = (
        db.query(QueryReport)
        .filter_by(fingerprint_id=str(fid))
        .order_by(QueryReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="no report generated yet")

    fp = db.query(QueryFingerprint).filter_by(id=str(fid)).first()
    findings = {"normalized_query": fp.normalized_query, "findings": []}
    return ReportResult(
        generated_text=report.generated_text,
        model_name=report.model_name,
        findings=findings,
    )
