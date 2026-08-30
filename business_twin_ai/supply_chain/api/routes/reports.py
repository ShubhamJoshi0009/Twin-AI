"""Supply Chain Reports API routes."""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.config import settings
from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.report import SupplyChainReportEngine
from business_twin_ai.supply_chain.schemas.schemas import (
    SupplyChainReportRequest,
    SupplyChainReportResponse,
)

router = APIRouter()


@router.post("/generate", response_model=SupplyChainReportResponse)
async def generate_report(
    request: SupplyChainReportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a supply chain report."""
    engine = SupplyChainReportEngine(db)
    return await engine.generate_report(request)


@router.get("/{report_id}/download")
async def download_report(report_id: uuid.UUID) -> FileResponse:
    """Download a previously generated supply chain report file."""
    for filename in (f"sc_{report_id}.pdf", f"sc_{report_id}.txt"):
        filepath = os.path.join(settings.REPORT_OUTPUT_DIR, filename)
        if os.path.isfile(filepath):
            media_type = "application/pdf" if filename.endswith(".pdf") else "text/plain"
            return FileResponse(filepath, media_type=media_type, filename=filename)
    raise HTTPException(status_code=404, detail="Report not found")
