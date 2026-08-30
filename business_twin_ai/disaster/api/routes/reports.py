"""Disaster report API routes (creation, validation, queries)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.disaster.engines.service import ValidationService
from business_twin_ai.disaster.models import DisasterReport
from business_twin_ai.disaster.schemas.schemas import (
    DisasterReportCreate,
    DisasterReportOut,
    ReportValidationResponse,
)

router = APIRouter()


@router.post("/reports", response_model=ReportValidationResponse, status_code=201)
async def create_report(
    payload: DisasterReportCreate,
    db: AsyncSession = Depends(get_db),
) -> ReportValidationResponse:
    """Create a report — validated, stored, clustered, trust + map updated.

    Note: the ValidationMiddleware also intercepts this path and runs the same
    service; this handler exists as the documented route and is what executes
    when the middleware is not installed (e.g. in tests or alternative hosts).
    """
    service = ValidationService(db)
    outcome = await service.submit_report(payload.model_dump(exclude_none=True))
    # Persist trust updates even for rejected reports (spec §8) — commit before
    # raising so get_db does not roll the session back.
    await db.commit()
    if outcome.rejected:
        raise HTTPException(status_code=422, detail=outcome.validation)
    return ReportValidationResponse(report_id=outcome.report_id, validation=outcome.validation)


@router.post("/validate-report", response_model=ReportValidationResponse)
async def validate_report(
    payload: DisasterReportCreate,
    db: AsyncSession = Depends(get_db),
) -> ReportValidationResponse:
    """Run the full validation pipeline without storing the report."""
    service = ValidationService(db)
    validation = await service.validate_only(payload.model_dump(exclude_none=True))
    return ReportValidationResponse(report_id=validation["report_id"], validation=validation)


@router.get("/report/{report_id}/validation", response_model=ReportValidationResponse)
async def get_report_validation(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReportValidationResponse:
    """Return the stored validation summary for a report."""
    report = await db.get(DisasterReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    validation = _stored_validation(report)
    return ReportValidationResponse(report_id=str(report.id), validation=validation)


@router.get("/reports/duplicates", response_model=list[DisasterReportOut])
async def list_duplicate_reports(db: AsyncSession = Depends(get_db)) -> list[DisasterReport]:
    """List stored reports flagged as duplicates."""
    result = await db.execute(
        select(DisasterReport)
        .where(DisasterReport.duplicate.is_(True))
        .order_by(DisasterReport.duplicate_score.desc())
        .limit(200)
    )
    return list(result.scalars().all())


@router.get("/reports/suspicious", response_model=list[DisasterReportOut])
async def list_suspicious_reports(db: AsyncSession = Depends(get_db)) -> list[DisasterReport]:
    """List stored reports flagged as suspicious/fake."""
    result = await db.execute(
        select(DisasterReport)
        .where(DisasterReport.suspicious.is_(True))
        .order_by(DisasterReport.created_at.desc())
        .limit(200)
    )
    return list(result.scalars().all())


def _stored_validation(report: DisasterReport) -> dict:
    """Rebuild the §9-shaped validation object from a stored report."""
    from business_twin_ai.disaster.config import config
    from business_twin_ai.disaster.utils.geo import precision_score

    precision = precision_score(report.latitude, report.longitude, config)
    return {
        "report_id": str(report.id),
        "valid": report.validation_status != "rejected",
        "confidence_score": report.confidence_score,
        "location_score": report.location_score,
        "metadata_score": report.metadata_score,
        "image_score": report.image_score,
        "duplicate": report.duplicate,
        "duplicate_score": report.duplicate_score,
        "suspicious": report.suspicious,
        "suspicious_reasons": [
            note for note in (report.validation_notes or []) if "suspicious" in note.lower()
        ],
        "cluster_id": report.cluster_id,
        "warning_level": report.warning_level,
        "validation_status": report.validation_status,
        "reporter_trust_score": report.reporter_trust_score,
        "execution_time_ms": 0.0,
        "location": {
            "valid_location": report.validation_status != "rejected",
            "precision_score": round(precision, 2),
            "location_verified": bool(report.location_name),
            "reason": None,
        },
        "metadata": {
            "metadata_score": report.metadata_score,
            "valid": report.metadata_score >= 30.0,
            "warnings": [],
        },
        "image": {
            "image_valid": report.image_score > 0,
            "image_score": report.image_score,
            "image_metadata": report.image_metadata or {},
        },
        "duplicate_details": {
            "duplicate": report.duplicate,
            "duplicate_score": report.duplicate_score,
            "duplicate_of": report.duplicate_of,
            "candidates_checked": 0,
        },
        "suspicious_details": {
            "suspicious": report.suspicious,
            "reasons": [
                note for note in (report.validation_notes or []) if "suspicious" in note.lower()
            ],
        },
        "confidence": {
            "confidence_score": report.confidence_score,
            "components": {
                "location": report.location_score,
                "metadata": report.metadata_score,
                "image": report.image_score,
                "duplicate": 100.0 - report.duplicate_score,
                "trust": report.reporter_trust_score,
            },
        },
        "validation_notes": report.validation_notes or [],
    }
