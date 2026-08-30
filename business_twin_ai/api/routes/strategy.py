"""API routes for Strategy generation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.strategy import StrategyEngine
from business_twin_ai.core.schemas.schemas import StrategyResponse
from business_twin_ai.database import get_db

router = APIRouter(prefix="/strategies", tags=["Strategy"])


@router.post("/{twin_id}/generate", response_model=StrategyResponse)
async def generate_strategies(
    twin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StrategyResponse:
    """Generate comprehensive business strategies for a digital twin."""
    engine = StrategyEngine(db)
    try:
        strategies = await engine.generate_strategies(twin_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return strategies
