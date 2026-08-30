"""Supplier Management API routes."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.supplier import SupplierEngine
from business_twin_ai.supply_chain.schemas.schemas import (
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)

router = APIRouter()


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(data: SupplierCreate, db: AsyncSession = Depends(get_db)):
    """Create a new supplier."""
    engine = SupplierEngine(db)
    supplier = await engine.create_supplier(data)
    return SupplierResponse.model_validate(supplier)


@router.get("", response_model=List[SupplierResponse])
async def list_suppliers(
    limit: int = 50,
    offset: int = 0,
    category: str = None,
    db: AsyncSession = Depends(get_db),
):
    """List suppliers."""
    engine = SupplierEngine(db)
    suppliers = await engine.list_suppliers(limit=limit, offset=offset, category=category)
    return [SupplierResponse.model_validate(s) for s in suppliers]


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a supplier by ID."""
    engine = SupplierEngine(db)
    supplier = await engine.get_supplier(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return SupplierResponse.model_validate(supplier)


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: uuid.UUID,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a supplier."""
    engine = SupplierEngine(db)
    supplier = await engine.update_supplier(supplier_id, data)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return SupplierResponse.model_validate(supplier)


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(supplier_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a supplier."""
    engine = SupplierEngine(db)
    deleted = await engine.delete_supplier(supplier_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Supplier not found")
