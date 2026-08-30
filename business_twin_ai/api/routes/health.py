"""API routes for Business Health Score."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.health import HealthEngine
from business_twin_ai.core.schemas.schemas import HealthScoreResponse
from business_twin_ai.database import get_db

router = APIRouter(prefix="/health", tags=["Business Health"])


@router.get("/{twin_id}", response_model=HealthScoreResponse)
async def get_health_score(
    twin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> HealthScoreResponse:
    """Calculate and return the business health score for a digital twin."""
    engine = HealthEngine(db)
    try:
        health = await engine.calculate_health(twin_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return health
