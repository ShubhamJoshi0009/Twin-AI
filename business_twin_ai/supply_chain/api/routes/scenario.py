"""Scenario Analysis API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.scenario import ScenarioEngine
from business_twin_ai.supply_chain.schemas.schemas import ScenarioRequest, ScenarioResponse

router = APIRouter()


@router.post("/simulate", response_model=ScenarioResponse)
async def simulate_scenario(request: ScenarioRequest, db: AsyncSession = Depends(get_db)):
    """Simulate a supply chain scenario."""
    engine = ScenarioEngine(db)
    try:
        return await engine.simulate_scenario(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/types")
async def list_scenario_types():
    """List available scenario types."""
    from business_twin_ai.supply_chain.engines.scenario import SCENARIO_TEMPLATES
    return {
        "scenarios": [
            {"type": k, "name": v["name"]}
            for k, v in SCENARIO_TEMPLATES.items()
        ]
    }
