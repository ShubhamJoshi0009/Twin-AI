"""Business Digital Twin engine.

Creates, updates, and maintains the digital representation of an enterprise.
The twin models all key business metrics and updates after every simulation.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.models.database import DigitalTwin
from business_twin_ai.core.schemas.schemas import BusinessData


class DigitalTwinEngine:
    """Manages the lifecycle of business digital twins."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_twin(self, data: BusinessData) -> DigitalTwin:
        """Create a new digital twin from structured business data."""
        twin = DigitalTwin(
            name=data.name,
            industry=data.industry,
            description=data.description,
            revenue=data.revenue,
            expenses=data.expenses,
            profit=data.profit or (data.revenue - data.expenses),
            cash_flow=data.cash_flow,
            customers=data.customers,
            employees=data.employees,
            products=data.products or {},
            sales=data.sales,
            marketing_budget=data.marketing_budget,
            pricing=data.pricing or {},
            inventory_summary=data.inventory_summary or {},
            warehouses=data.warehouses or {},
            competitors=data.competitors or {},
            market_share=data.market_share,
            kpis=data.kpis or {},
            raw_data=data.raw_data or {},
        )

        # Auto-calculate derived metrics
        twin.profit = data.revenue - data.expenses
        twin.kpis = self._compute_kpis(twin)

        self.db.add(twin)
        await self.db.flush()
        await self.db.refresh(twin)
        return twin

    async def get_twin(self, twin_id: uuid.UUID) -> Optional[DigitalTwin]:
        """Retrieve a digital twin by ID."""
        result = await self.db.execute(select(DigitalTwin).where(DigitalTwin.id == twin_id))
        return result.scalar_one_or_none()

    async def update_twin(self, twin_id: uuid.UUID, data: BusinessData) -> Optional[DigitalTwin]:
        """Update an existing digital twin with new business data."""
        twin = await self.get_twin(twin_id)
        if not twin:
            return None

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if hasattr(twin, field) and field not in ("id", "created_at", "updated_at"):
                setattr(twin, field, value)

        # Recalculate derived metrics
        twin.profit = twin.revenue - twin.expenses
        twin.kpis = self._compute_kpis(twin)

        await self.db.flush()
        await self.db.refresh(twin)
        return twin

    async def update_twin_state(self, twin_id: uuid.UUID, state_updates: Dict[str, Any]) -> Optional[DigitalTwin]:
        """Apply partial state updates after a simulation."""
        twin = await self.get_twin(twin_id)
        if not twin:
            return None

        for field, value in state_updates.items():
            if hasattr(twin, field) and field not in ("id", "created_at", "updated_at"):
                setattr(twin, field, value)

        twin.profit = twin.revenue - twin.expenses
        twin.kpis = self._compute_kpis(twin)

        await self.db.flush()
        await self.db.refresh(twin)
        return twin

    async def list_twins(self, limit: int = 50, offset: int = 0) -> list[DigitalTwin]:
        """List all digital twins with pagination."""
        result = await self.db.execute(
            select(DigitalTwin).order_by(DigitalTwin.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def delete_twin(self, twin_id: uuid.UUID) -> bool:
        """Delete a digital twin and all associated data."""
        twin = await self.get_twin(twin_id)
        if not twin:
            return False
        await self.db.delete(twin)
        await self.db.flush()
        return True

    def get_twin_state(self, twin: DigitalTwin) -> Dict[str, Any]:
        """Extract the current state of a twin as a dictionary for AI prompts."""
        return {
            "name": twin.name,
            "industry": twin.industry,
            "revenue": twin.revenue,
            "expenses": twin.expenses,
            "profit": twin.profit,
            "cash_flow": twin.cash_flow,
            "customers": twin.customers,
            "employees": twin.employees,
            "products": twin.products or {},
            "sales": twin.sales,
            "marketing_budget": twin.marketing_budget,
            "pricing": twin.pricing or {},
            "inventory_summary": twin.inventory_summary or {},
            "warehouses": twin.warehouses or {},
            "competitors": twin.competitors or {},
            "market_share": twin.market_share,
            "kpis": twin.kpis or {},
            "business_health_score": twin.business_health_score,
        }

    def _compute_kpis(self, twin: DigitalTwin) -> Dict[str, Any]:
        """Compute key performance indicators from the current state."""
        profit_margin = (twin.profit / twin.revenue * 100) if twin.revenue > 0 else 0
        revenue_per_employee = twin.revenue / twin.employees if twin.employees > 0 else 0
        customer_acquisition_cost = (
            twin.marketing_budget / twin.customers if twin.customers > 0 else 0
        )
        revenue_per_customer = twin.revenue / twin.customers if twin.customers > 0 else 0
        operating_expense_ratio = (twin.expenses / twin.revenue * 100) if twin.revenue > 0 else 0

        return {
            "profit_margin": round(profit_margin, 2),
            "revenue_per_employee": round(revenue_per_employee, 2),
            "customer_acquisition_cost": round(customer_acquisition_cost, 2),
            "revenue_per_customer": round(revenue_per_customer, 2),
            "operating_expense_ratio": round(operating_expense_ratio, 2),
            "cash_flow_ratio": round((twin.cash_flow / twin.revenue * 100) if twin.revenue > 0 else 0, 2),
            "marketing_roi": round((twin.sales / twin.marketing_budget) if twin.marketing_budget > 0 else 0, 2),
            "employee_productivity": round(revenue_per_employee, 2),
        }
