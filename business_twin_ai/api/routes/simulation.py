"""API routes for simulation and what-if analysis."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.simulator import VALID_DECISIONS, SimulatorEngine
from business_twin_ai.core.engines.whatif import WhatIfEngine
from business_twin_ai.core.schemas.schemas import (
    DecisionRequest,
    SimulationResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from business_twin_ai.database import get_db

router = APIRouter(prefix="/simulations", tags=["Simulation"])


@router.post("/{twin_id}/run", response_model=SimulationResponse)
async def run_simulation(
    twin_id: uuid.UUID,
    request: DecisionRequest,
    db: AsyncSession = Depends(get_db),
) -> SimulationResponse:
    """Run a simulation for a business decision on the given digital twin."""
    engine = SimulatorEngine(db)
    try:
        sim = await engine.run_simulation(twin_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return SimulationResponse(
        id=sim.id,
        twin_id=sim.twin_id,
        decision_type=sim.decision_type,
        decision_params=sim.decision_params or {},
        predictions=sim.predictions or {},
        scenarios=sim.scenarios or [],
        confidence=sim.confidence_details or {},
        recommendation=sim.recommendation or {},
        explanation=sim.explanation or {},
        created_at=sim.created_at,
    )


@router.post("/{twin_id}/compare", response_model=WhatIfResponse)
async def compare_scenarios(
    twin_id: uuid.UUID,
    request: WhatIfRequest,
    db: AsyncSession = Depends(get_db),
) -> WhatIfResponse:
    """Compare multiple what-if scenarios side by side."""
    engine = WhatIfEngine(db)
    try:
        result = await engine.compare_scenarios(twin_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@router.get("/decision-types")
async def list_decision_types() -> dict:
    """List all available decision types and their descriptions."""
    return {
        "decision_types": [
            {"type": k, "description": v.get("description", "")}
            for k, v in VALID_DECISIONS.items()
        ]
    }
