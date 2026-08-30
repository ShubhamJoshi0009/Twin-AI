"""API routes for Business Timeline — stores and replays simulations."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.models.database import Simulation
from business_twin_ai.core.schemas.schemas import SimulationResponse, TimelineEntry
from business_twin_ai.database import get_db

router = APIRouter(prefix="/timeline", tags=["Timeline"])


def _to_timeline_entry(s: Simulation) -> TimelineEntry:
    """Map a stored Simulation row to the timeline entry shape the frontend consumes."""
    return TimelineEntry(
        simulation_id=s.id,
        decision_type=s.decision_type,
        decision_params=s.decision_params or {},
        predicted_revenue=s.predicted_revenue,
        predicted_profit=s.predicted_profit,
        confidence_score=s.confidence_score,
        recommendation=s.recommendation or {},
        created_at=s.created_at,
    )


@router.get("/{twin_id}", response_model=List[TimelineEntry])
async def get_timeline(
    twin_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> List[TimelineEntry]:
    """Get the simulation timeline for a digital twin."""
    result = await db.execute(
        select(Simulation)
        .where(Simulation.twin_id == twin_id)
        .order_by(Simulation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    simulations = result.scalars().all()
    return [_to_timeline_entry(s) for s in simulations]


@router.get("/{twin_id}/{simulation_id}", response_model=SimulationResponse)
async def replay_simulation(
    twin_id: uuid.UUID,
    simulation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SimulationResponse:
    """Replay (retrieve) a specific simulation from the timeline."""
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.twin_id == twin_id,
        )
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")

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
