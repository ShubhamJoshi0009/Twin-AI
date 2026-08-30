"""Logistics and Shipment API routes."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.logistics import LogisticsEngine
from business_twin_ai.supply_chain.schemas.schemas import (
    RouteOptimizationResponse,
    ShipmentCreate,
    ShipmentResponse,
    ShipmentUpdate,
)

router = APIRouter()


@router.post("", response_model=ShipmentResponse, status_code=201)
async def create_shipment(data: ShipmentCreate, db: AsyncSession = Depends(get_db)):
    """Create a new shipment."""
    engine = LogisticsEngine(db)
    shipment = await engine.create_shipment(data)
    return ShipmentResponse.model_validate(shipment)


@router.get("", response_model=List[ShipmentResponse])
async def list_shipments(
    status: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List shipments."""
    engine = LogisticsEngine(db)
    shipments = await engine.list_shipments(status=status, limit=limit)
    return [ShipmentResponse.model_validate(s) for s in shipments]


@router.get("/delayed", response_model=List[ShipmentResponse])
async def get_delayed_shipments(db: AsyncSession = Depends(get_db)):
    """Get all delayed shipments."""
    engine = LogisticsEngine(db)
    shipments = await engine.get_delayed_shipments()
    return [ShipmentResponse.model_validate(s) for s in shipments]


@router.post("/optimize-routes", response_model=RouteOptimizationResponse)
async def optimize_routes(db: AsyncSession = Depends(get_db)):
    """Optimize delivery routes."""
    engine = LogisticsEngine(db)
    return await engine.optimize_routes()


@router.get("/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(shipment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a shipment by ID."""
    engine = LogisticsEngine(db)
    shipment = await engine.get_shipment(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return ShipmentResponse.model_validate(shipment)


@router.put("/{shipment_id}", response_model=ShipmentResponse)
async def update_shipment(
    shipment_id: uuid.UUID,
    data: ShipmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update shipment status."""
    engine = LogisticsEngine(db)
    shipment = await engine.update_shipment(shipment_id, data)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return ShipmentResponse.model_validate(shipment)
