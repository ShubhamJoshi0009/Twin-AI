"""Inventory Management engine.

Tracks stock levels, detects anomalies, and optimizes inventory.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.supply_chain.models.database import InventoryItem, Warehouse
from business_twin_ai.supply_chain.prompts.templates import (
    SC_INVENTORY_OPT_SYSTEM,
    SC_INVENTORY_OPT_USER,
    format_prompt,
)
from business_twin_ai.supply_chain.schemas.schemas import (
    InventoryCreate,
    InventoryOptimization,
    InventoryOptimizationResponse,
    InventoryUpdate,
)


class InventoryEngine:
    """Manages inventory tracking and optimization."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_client()

    async def create_inventory(self, data: InventoryCreate) -> InventoryItem:
        """Create a new inventory item."""
        item = InventoryItem(
            warehouse_id=data.warehouse_id,
            product_name=data.product_name,
            product_sku=data.product_sku,
            category=data.category,
            current_stock=data.current_stock,
            reorder_level=data.reorder_level,
            safety_stock=data.safety_stock,
            max_stock=data.max_stock,
            unit_cost=data.unit_cost,
            expiry_date=data.expiry_date,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def get_inventory(self, item_id: uuid.UUID) -> Optional[InventoryItem]:
        """Get inventory item by ID."""
        result = await self.db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
        return result.scalar_one_or_none()

    async def update_inventory(self, item_id: uuid.UUID, data: InventoryUpdate) -> Optional[InventoryItem]:
        """Update inventory item."""
        item = await self.get_inventory(item_id)
        if not item:
            return None

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if hasattr(item, field) and field not in ("id", "created_at", "updated_at"):
                setattr(item, field, value)

        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def list_inventory(
        self, warehouse_id: Optional[uuid.UUID] = None, limit: int = 100
    ) -> List[InventoryItem]:
        """List inventory items."""
        query = select(InventoryItem)
        if warehouse_id:
            query = query.where(InventoryItem.warehouse_id == warehouse_id)
        query = query.limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect inventory anomalies (low stock, overstock, dead stock, etc.)."""
        items = await self.list_inventory()
        anomalies = []

        for item in items:
            available = item.current_stock - item.reserved_stock
            status = self._get_stock_status(item)

            if status != "normal":
                anomalies.append({
                    "item_id": str(item.id),
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "status": status,
                    "current_stock": item.current_stock,
                    "reorder_level": item.reorder_level,
                    "message": self._get_anomaly_message(item, status),
                })

        return anomalies

    async def optimize_inventory(self) -> InventoryOptimizationResponse:
        """Generate inventory optimization recommendations."""
        items = await self.list_inventory()
        warehouses_result = await self.db.execute(select(Warehouse))
        warehouses = {str(w.id): w for w in warehouses_result.scalars().all()}

        # Try LLM optimization
        try:
            return await self._llm_optimize(items, warehouses)
        except Exception:
            return self._rule_based_optimize(items, warehouses)

    def _get_stock_status(self, item: InventoryItem) -> str:
        """Determine stock status."""
        available = item.current_stock - item.reserved_stock

        if available <= 0:
            return "stockout"
        elif available <= item.safety_stock:
            return "critical_low"
        elif available <= item.reorder_level:
            return "low_stock"
        elif item.current_stock >= item.max_stock * 0.9:
            return "overstock"
        elif item.turnover_rate < 0.1:
            return "dead_stock"
        elif item.turnover_rate > 5.0:
            return "fast_moving"
        elif item.turnover_rate < 0.5:
            return "slow_moving"
        return "normal"

    def _get_anomaly_message(self, item: InventoryItem, status: str) -> str:
        """Generate anomaly message."""
        messages = {
            "stockout": f"{item.product_name} is OUT OF STOCK!",
            "critical_low": f"{item.product_name} is critically low ({item.current_stock} units)",
            "low_stock": f"{item.product_name} is below reorder level",
            "overstock": f"{item.product_name} is overstocked ({item.current_stock}/{item.max_stock})",
            "dead_stock": f"{item.product_name} has very low turnover (dead stock)",
            "fast_moving": f"{item.product_name} is moving fast — consider increasing stock",
            "slow_moving": f"{item.product_name} has slow movement — consider promotion",
        }
        return messages.get(status, f"{item.product_name} status: {status}")

    async def _llm_optimize(
        self, items: List[InventoryItem], warehouses: Dict[str, Warehouse]
    ) -> InventoryOptimizationResponse:
        """LLM-based inventory optimization."""
        inventory_data = [
            {
                "name": i.product_name,
                "sku": i.product_sku,
                "stock": i.current_stock,
                "reorder": i.reorder_level,
                "max": i.max_stock,
                "turnover": i.turnover_rate,
            }
            for i in items[:20]
        ]
        warehouse_data = [
            {"name": w.name, "capacity": w.capacity, "utilization": w.utilization}
            for w in warehouses.values()
        ]

        prompt = format_prompt(
            SC_INVENTORY_OPT_USER,
            current_inventory=str(inventory_data),
            warehouse_status=str(warehouse_data),
            demand_patterns="Historical demand patterns available",
        )
        data = await self.llm.chat_json(SC_INVENTORY_OPT_SYSTEM, prompt)
        return InventoryOptimizationResponse(**data)

    def _rule_based_optimize(
        self, items: List[InventoryItem], warehouses: Dict[str, Warehouse]
    ) -> InventoryOptimizationResponse:
        """Rule-based inventory optimization."""
        optimizations = []
        total_saving = 0.0

        for item in items:
            status = self._get_stock_status(item)
            if status in ("stockout", "critical_low", "low_stock"):
                reorder_qty = max(item.reorder_level - item.current_stock, item.safety_stock)
                saving = reorder_qty * item.unit_cost * 0.05  # 5% efficiency gain
                total_saving += saving

                optimizations.append(InventoryOptimization(
                    product_name=item.product_name,
                    product_sku=item.product_sku,
                    warehouse_name="Current Warehouse",
                    current_stock=item.current_stock,
                    recommended_reorder=reorder_qty,
                    optimal_safety_stock=item.reorder_level,
                    transfer_quantity=None,
                    transfer_from=None,
                    transfer_to=None,
                    urgency="immediate" if status in ("stockout", "critical_low") else "soon",
                    estimated_cost_saving=round(saving, 2),
                ))
            elif status == "overstock":
                excess = item.current_stock - int(item.max_stock * 0.7)
                if excess > 0:
                    saving = excess * item.unit_cost * 0.02
                    total_saving += saving
                    optimizations.append(InventoryOptimization(
                        product_name=item.product_name,
                        product_sku=item.product_sku,
                        warehouse_name="Current Warehouse",
                        current_stock=item.current_stock,
                        recommended_reorder=0,
                        optimal_safety_stock=item.safety_stock,
                        transfer_quantity=excess,
                        transfer_from=None,
                        transfer_to=None,
                        urgency="normal",
                        estimated_cost_saving=round(saving, 2),
                    ))

        score = max(0, 100 - len(optimizations) * 10)

        return InventoryOptimizationResponse(
            optimizations=optimizations,
            optimization_score=score,
            total_potential_saving=round(total_saving, 2),
            generated_at=datetime.now(timezone.utc),
        )
