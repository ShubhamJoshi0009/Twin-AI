"""Supplier Management engine.

Handles supplier CRUD, performance scoring, and recommendations.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.supply_chain.models.database import Supplier
from business_twin_ai.supply_chain.schemas.schemas import (
    SupplierCreate,
    SupplierUpdate,
)


class SupplierEngine:
    """Manages supplier lifecycle and scoring."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_supplier(self, data: SupplierCreate) -> Supplier:
        """Create a new supplier."""
        supplier = Supplier(
            name=data.name,
            contact_name=data.contact_name,
            email=data.email,
            phone=data.phone,
            location=data.location,
            country=data.country,
            product_categories=data.product_categories or [],
            lead_time_days=data.lead_time_days,
            cost_per_unit=data.cost_per_unit,
            capacity=data.capacity,
            quality_rating=data.quality_rating,
            contract_expiry=data.contract_expiry,
            reliability_score=self._calc_reliability(data),
            risk_score=self._calc_initial_risk(data),
        )
        self.db.add(supplier)
        await self.db.flush()
        await self.db.refresh(supplier)
        return supplier

    async def get_supplier(self, supplier_id: uuid.UUID) -> Optional[Supplier]:
        """Get a supplier by ID."""
        result = await self.db.execute(select(Supplier).where(Supplier.id == supplier_id))
        return result.scalar_one_or_none()

    async def update_supplier(self, supplier_id: uuid.UUID, data: SupplierUpdate) -> Optional[Supplier]:
        """Update a supplier."""
        supplier = await self.get_supplier(supplier_id)
        if not supplier:
            return None

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if hasattr(supplier, field) and field not in ("id", "created_at", "updated_at"):
                setattr(supplier, field, value)

        supplier.reliability_score = self._calc_reliability_from_supplier(supplier)
        await self.db.flush()
        await self.db.refresh(supplier)
        return supplier

    async def delete_supplier(self, supplier_id: uuid.UUID) -> bool:
        """Delete a supplier."""
        supplier = await self.get_supplier(supplier_id)
        if not supplier:
            return False
        await self.db.delete(supplier)
        await self.db.flush()
        return True

    async def list_suppliers(
        self, limit: int = 50, offset: int = 0, category: Optional[str] = None
    ) -> List[Supplier]:
        """List suppliers with optional category filter."""
        query = select(Supplier).where(Supplier.is_active == True)
        if category:
            query = query.where(Supplier.product_categories.contains([category]))
        query = query.order_by(Supplier.reliability_score.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_supplier_state(self, supplier_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get supplier state as dictionary for AI prompts."""
        supplier = await self.get_supplier(supplier_id)
        if not supplier:
            return None
        return {
            "name": supplier.name,
            "location": supplier.location,
            "lead_time_days": supplier.lead_time_days,
            "cost_per_unit": supplier.cost_per_unit,
            "capacity": supplier.capacity,
            "quality_rating": supplier.quality_rating,
            "reliability_score": supplier.reliability_score,
            "risk_score": supplier.risk_score,
            "product_categories": supplier.product_categories or [],
        }

    def _calc_reliability(self, data: SupplierCreate) -> float:
        """Calculate initial reliability score."""
        score = 50.0
        if data.quality_rating >= 4:
            score += 20
        elif data.quality_rating >= 3:
            score += 10
        if data.lead_time_days <= 7:
            score += 15
        elif data.lead_time_days <= 14:
            score += 5
        if data.capacity >= 1000:
            score += 10
        return min(100, max(0, score))

    def _calc_reliability_from_supplier(self, supplier: Supplier) -> float:
        """Recalculate reliability from supplier data."""
        score = 50.0
        if supplier.quality_rating >= 4:
            score += 20
        elif supplier.quality_rating >= 3:
            score += 10
        if supplier.lead_time_days <= 7:
            score += 15
        elif supplier.lead_time_days <= 14:
            score += 5
        if supplier.capacity >= 1000:
            score += 10
        return min(100, max(0, score))

    def _calc_initial_risk(self, data: SupplierCreate) -> float:
        """Calculate initial risk score (lower is better)."""
        risk = 30.0
        if data.lead_time_days > 14:
            risk += 20
        if data.quality_rating < 3:
            risk += 25
        if data.capacity < 500:
            risk += 15
        return min(100, max(0, risk))
