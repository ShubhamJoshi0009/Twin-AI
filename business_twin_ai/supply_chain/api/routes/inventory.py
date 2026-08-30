"""Inventory Management API routes."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.inventory import InventoryEngine
from business_twin_ai.supply_chain.schemas.schemas import (
    InventoryCreate,
    InventoryOptimizationResponse,
    InventoryResponse,
    InventoryUpdate,
)

router = APIRouter()


def _to_response(item) -> InventoryResponse:
    """Convert ORM item to response with computed fields."""
    available = item.current_stock - item.reserved_stock
    # Determine status
    if available <= 0:
        status = "stockout"
    elif available <= item.safety_stock:
        status = "critical_low"
    elif available <= item.reorder_level:
        status = "low_stock"
    elif item.current_stock >= item.max_stock * 0.9:
        status = "overstock"
    elif item.turnover_rate > 5.0:
        status = "fast_moving"
    elif item.turnover_rate < 0.5:
        status = "slow_moving"
    else:
        status = "normal"

    return InventoryResponse(
        id=item.id,
        warehouse_id=item.warehouse_id,
        product_name=item.product_name,
        product_sku=item.product_sku,
        category=item.category,
        current_stock=item.current_stock,
        reorder_level=item.reorder_level,
        safety_stock=item.safety_stock,
        max_stock=item.max_stock,
        incoming_stock=item.incoming_stock,
        reserved_stock=item.reserved_stock,
        available_stock=available,
        unit_cost=item.unit_cost,
        turnover_rate=item.turnover_rate,
        expiry_date=item.expiry_date,
        status=status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("", response_model=InventoryResponse, status_code=201)
async def create_inventory(data: InventoryCreate, db: AsyncSession = Depends(get_db)):
    """Create a new inventory item."""
    engine = InventoryEngine(db)
    item = await engine.create_inventory(data)
    return _to_response(item)


@router.get("", response_model=List[InventoryResponse])
async def list_inventory(
    warehouse_id: uuid.UUID = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List inventory items."""
    engine = InventoryEngine(db)
    items = await engine.list_inventory(warehouse_id=warehouse_id, limit=limit)
    return [_to_response(i) for i in items]


@router.get("/anomalies")
async def detect_anomalies(db: AsyncSession = Depends(get_db)):
    """Detect inventory anomalies."""
    engine = InventoryEngine(db)
    anomalies = await engine.detect_anomalies()
    return {"anomalies": anomalies, "count": len(anomalies)}


@router.post("/optimize", response_model=InventoryOptimizationResponse)
async def optimize_inventory(db: AsyncSession = Depends(get_db)):
    """Generate inventory optimization recommendations."""
    engine = InventoryEngine(db)
    return await engine.optimize_inventory()


@router.get("/{item_id}", response_model=InventoryResponse)
async def get_inventory(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get an inventory item."""
    engine = InventoryEngine(db)
    item = await engine.get_inventory(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return _to_response(item)


@router.put("/{item_id}", response_model=InventoryResponse)
async def update_inventory(
    item_id: uuid.UUID,
    data: InventoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an inventory item."""
    engine = InventoryEngine(db)
    item = await engine.update_inventory(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return _to_response(item)
