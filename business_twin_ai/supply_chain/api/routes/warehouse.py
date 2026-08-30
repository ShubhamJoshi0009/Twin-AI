"""Warehouse Management API routes."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.warehouse import WarehouseEngine
from business_twin_ai.supply_chain.schemas.schemas import (
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUtilizationReport,
)

router = APIRouter()


@router.post("", response_model=WarehouseResponse, status_code=201)
async def create_warehouse(data: WarehouseCreate, db: AsyncSession = Depends(get_db)):
    """Create a new warehouse."""
    engine = WarehouseEngine(db)
    warehouse = await engine.create_warehouse(data)
    return WarehouseResponse.model_validate(warehouse)


@router.get("", response_model=List[WarehouseResponse])
async def list_warehouses(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """List all warehouses."""
    engine = WarehouseEngine(db)
    warehouses = await engine.list_warehouses(limit=limit)
    return [WarehouseResponse.model_validate(w) for w in warehouses]


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(warehouse_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a warehouse by ID."""
    engine = WarehouseEngine(db)
    warehouse = await engine.get_warehouse(warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return WarehouseResponse.model_validate(warehouse)


@router.get("/{warehouse_id}/utilization", response_model=WarehouseUtilizationReport)
async def get_utilization_report(warehouse_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get warehouse utilization report."""
    engine = WarehouseEngine(db)
    report = await engine.get_utilization_report(warehouse_id)
    if not report:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return report


@router.post("/{warehouse_id}/update-utilization", response_model=WarehouseResponse)
async def update_utilization(warehouse_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Recalculate warehouse utilization."""
    engine = WarehouseEngine(db)
    warehouse = await engine.update_utilization(warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return WarehouseResponse.model_validate(warehouse)
