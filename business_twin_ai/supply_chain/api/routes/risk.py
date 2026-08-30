"""Risk Detection and Prediction API routes."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.risk import RiskEngine
from business_twin_ai.supply_chain.schemas.schemas import RiskPredictionResponse, RiskResponse

router = APIRouter()


@router.post("/detect", response_model=List[RiskResponse])
async def detect_risks(db: AsyncSession = Depends(get_db)):
    """Scan and detect all active supply chain risks."""
    engine = RiskEngine(db)
    return await engine.detect_risks()


@router.get("", response_model=List[RiskResponse])
async def get_active_risks(db: AsyncSession = Depends(get_db)):
    """Get all active risks."""
    engine = RiskEngine(db)
    return await engine.get_active_risks()


@router.post("/predict", response_model=RiskPredictionResponse)
async def predict_risks(db: AsyncSession = Depends(get_db)):
    """Predict future supply chain risks."""
    engine = RiskEngine(db)
    return await engine.predict_risks()
