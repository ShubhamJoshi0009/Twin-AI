"""Supply Chain Alerts API routes."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.alerts import AlertEngine
from business_twin_ai.supply_chain.schemas.schemas import AlertResponse

router = APIRouter()


@router.post("/generate", response_model=List[AlertResponse])
async def generate_alerts(db: AsyncSession = Depends(get_db)):
    """Generate fresh supply chain alerts."""
    engine = AlertEngine(db)
    return await engine.generate_alerts()


@router.get("", response_model=List[AlertResponse])
async def get_active_alerts(db: AsyncSession = Depends(get_db)):
    """Get all active alerts."""
    engine = AlertEngine(db)
    return await engine.get_active_alerts()


@router.put("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Acknowledge an alert."""
    engine = AlertEngine(db)
    alert = await engine.acknowledge_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.put("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Resolve an alert."""
    engine = AlertEngine(db)
    alert = await engine.resolve_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
