"""API routes for Business Insights."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.insights import InsightsEngine
from business_twin_ai.core.schemas.schemas import InsightResponse
from business_twin_ai.database import get_db

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.post("/{twin_id}/generate", response_model=List[InsightResponse])
async def generate_insights(
    twin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> List[InsightResponse]:
    """Generate fresh business insights for a digital twin."""
    engine = InsightsEngine(db)
    try:
        insights = await engine.generate_insights(twin_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return insights


@router.get("/{twin_id}", response_model=List[InsightResponse])
async def get_insights(
    twin_id: uuid.UUID,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> List[InsightResponse]:
    """Get existing insights for a digital twin."""
    engine = InsightsEngine(db)
    try:
        insights = await engine.get_insights(twin_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return insights
