"""Warehouse Management engine.

Handles warehouse CRUD, utilization tracking, and reporting.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.supply_chain.models.database import InventoryItem, Warehouse
from business_twin_ai.supply_chain.schemas.schemas import (
    WarehouseCreate,
    WarehouseUtilizationReport,
)


class WarehouseEngine:
    """Manages warehouse operations and utilization."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_warehouse(self, data: WarehouseCreate) -> Warehouse:
        """Create a new warehouse."""
        warehouse = Warehouse(
            name=data.name,
            location=data.location,
            capacity=data.capacity,
            storage_cost_per_unit=data.storage_cost_per_unit,
            manager=data.manager,
        )
        self.db.add(warehouse)
        await self.db.flush()
        await self.db.refresh(warehouse)
        return warehouse

    async def get_warehouse(self, warehouse_id: uuid.UUID) -> Optional[Warehouse]:
        """Get a warehouse by ID."""
        result = await self.db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))
        return result.scalar_one_or_none()

    async def list_warehouses(self, limit: int = 50) -> List[Warehouse]:
        """List all warehouses."""
        result = await self.db.execute(
            select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.name)
        )
        return list(result.scalars().all())

    async def update_utilization(self, warehouse_id: uuid.UUID) -> Optional[Warehouse]:
        """Recalculate warehouse utilization from inventory data."""
        warehouse = await self.get_warehouse(warehouse_id)
        if not warehouse:
            return None

        # Calculate total stock in warehouse
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.warehouse_id == warehouse_id)
        )
        items = result.scalars().all()
        total_stock = sum(item.current_stock for item in items)

        warehouse.utilization = (total_stock / warehouse.capacity * 100) if warehouse.capacity > 0 else 0

        # Calculate efficiency
        if warehouse.utilization > 0:
            warehouse.efficiency_score = min(100, max(0, 100 - abs(warehouse.utilization - 75) * 2))
        else:
            warehouse.efficiency_score = 50.0

        await self.db.flush()
        await self.db.refresh(warehouse)
        return warehouse

    async def get_utilization_report(self, warehouse_id: uuid.UUID) -> Optional[WarehouseUtilizationReport]:
        """Generate utilization report for a warehouse."""
        warehouse = await self.get_warehouse(warehouse_id)
        if not warehouse:
            return None

        # Get inventory summary
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.warehouse_id == warehouse_id)
        )
        items = result.scalars().all()
        total_stock = sum(item.current_stock for item in items)

        # Calculate storage cost
        storage_cost = total_stock * warehouse.storage_cost_per_unit

        # Determine trend
        if warehouse.utilization > 85:
            trend = "overloaded"
        elif warehouse.utilization > 60:
            trend = "optimal"
        elif warehouse.utilization > 30:
            trend = "underutilized"
        else:
            trend = "empty"

        # Generate recommendations
        recommendations = []
        if warehouse.utilization > 90:
            recommendations.append("Warehouse is near capacity — consider redistributing inventory to other locations.")
        elif warehouse.utilization > 75:
            recommendations.append("Warehouse is at optimal utilization levels.")
        elif warehouse.utilization < 30:
            recommendations.append("Warehouse is underutilized — consider consolidating inventory or reducing storage costs.")
        if len(items) > 50:
            recommendations.append("Consider implementing zone-based storage for better efficiency.")

        return WarehouseUtilizationReport(
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            capacity=warehouse.capacity,
            current_utilization=round(warehouse.utilization, 1),
            utilization_trend=trend,
            storage_cost=round(storage_cost, 2),
            efficiency_score=round(warehouse.efficiency_score, 1),
            recommendations=recommendations,
        )
