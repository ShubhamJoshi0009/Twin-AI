"""Optimization Engine API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.optimization import OptimizationEngine
from business_twin_ai.supply_chain.schemas.schemas import OptimizationResponse

router = APIRouter()


@router.post("", response_model=OptimizationResponse)
async def run_optimization(db: AsyncSession = Depends(get_db)):
    """Run full supply chain optimization."""
    engine = OptimizationEngine(db)
    return await engine.optimize()
