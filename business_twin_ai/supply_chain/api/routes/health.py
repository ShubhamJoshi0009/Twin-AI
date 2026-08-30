"""Supply Chain Health Score API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.health import SupplyChainHealthEngine
from business_twin_ai.supply_chain.schemas.schemas import SupplyChainHealthResponse

router = APIRouter()


@router.get("", response_model=SupplyChainHealthResponse)
async def get_supply_chain_health(db: AsyncSession = Depends(get_db)):
    """Calculate supply chain health score."""
    engine = SupplyChainHealthEngine(db)
    return await engine.calculate_health()
