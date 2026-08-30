"""API routes for Report generation and download."""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.config import settings
from business_twin_ai.core.engines.report import ReportEngine
from business_twin_ai.core.schemas.schemas import ReportRequest, ReportResponse
from business_twin_ai.database import get_db

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/{twin_id}/generate", response_model=ReportResponse)
async def generate_report(
    twin_id: uuid.UUID,
    request: ReportRequest,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Generate a downloadable PDF report for a digital twin."""
    engine = ReportEngine(db)
    try:
        report = await engine.generate_report(twin_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return report


@router.get("/{report_id}/download")
async def download_report(report_id: uuid.UUID) -> FileResponse:
    """Download a previously generated report file (PDF, or .txt placeholder)."""
    for filename in (f"{report_id}.pdf", f"{report_id}.txt"):
        filepath = os.path.join(settings.REPORT_OUTPUT_DIR, filename)
        if os.path.isfile(filepath):
            media_type = "application/pdf" if filename.endswith(".pdf") else "text/plain"
            return FileResponse(filepath, media_type=media_type, filename=filename)
    raise HTTPException(status_code=404, detail="Report not found")
