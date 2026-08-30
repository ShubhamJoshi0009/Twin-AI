"""Supply Chain Alerts engine.

Generates and manages real-time supply chain alerts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.supply_chain.models.database import (
    InventoryItem,
    Shipment,
    Supplier,
    SupplyChainAlert,
    Warehouse,
)
from business_twin_ai.supply_chain.schemas.schemas import AlertResponse


class AlertEngine:
    """Generates and manages supply chain alerts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_alerts(self) -> List[AlertResponse]:
        """Scan supply chain and generate alerts."""
        alerts_data = []

        # Supplier alerts
        suppliers = (await self.db.execute(
            select(Supplier).where(Supplier.is_active == True)
        )).scalars().all()

        for s in suppliers:
            if s.reliability_score < 50:
                alerts_data.append(self._make_alert(
                    "supplier_risk", "critical",
                    f"Critical: Supplier {s.name} Reliability Alert",
                    f"Supplier {s.name} reliability score dropped to {s.reliability_score}/100. Immediate review required.",
                    "Review supplier performance and consider alternative suppliers.",
                ))
            if s.contract_expiry:
                # Simple check - in production use proper date parsing
                alerts_data.append(self._make_alert(
                    "supplier_risk", "warning",
                    f"Contract Expiring: {s.name}",
                    f"Contract for {s.name} is expiring soon.",
                    "Initiate contract renewal discussions.",
                ))

        # Inventory alerts
        inventory = (await self.db.execute(select(InventoryItem))).scalars().all()
        for item in inventory:
            available = item.current_stock - item.reserved_stock
            if available <= 0:
                alerts_data.append(self._make_alert(
                    "inventory_shortage", "critical",
                    f"CRITICAL: {item.product_name} Out of Stock",
                    f"{item.product_name} (SKU: {item.product_sku}) is completely out of stock.",
                    "Place emergency reorder immediately.",
                ))
            elif available <= item.safety_stock:
                alerts_data.append(self._make_alert(
                    "inventory_shortage", "warning",
                    f"Low Stock Alert: {item.product_name}",
                    f"{item.product_name} below safety stock ({available} units remaining).",
                    "Schedule reorder to prevent stockout.",
                ))

        # Warehouse alerts
        warehouses = (await self.db.execute(
            select(Warehouse).where(Warehouse.is_active == True)
        )).scalars().all()
        for w in warehouses:
            if w.utilization > 90:
                alerts_data.append(self._make_alert(
                    "warehouse_overload", "warning",
                    f"Warehouse Near Capacity: {w.name}",
                    f"Warehouse {w.name} at {w.utilization:.0f}% utilization.",
                    "Consider redistributing inventory to other warehouses.",
                ))

        # Shipment alerts
        delayed = (await self.db.execute(
            select(Shipment).where(Shipment.status == "delayed")
        )).scalars().all()
        for s in delayed:
            alerts_data.append(self._make_alert(
                "shipment_delay", "warning",
                f"Shipment Delayed: {s.shipment_number}",
                f"Shipment {s.shipment_number} from {s.origin} to {s.destination} is delayed.",
                "Contact carrier for updated ETA and notify stakeholders.",
            ))

        # Persist and return
        results = []
        for alert_data in alerts_data:
            alert = SupplyChainAlert(**alert_data)
            self.db.add(alert)
            await self.db.flush()
            await self.db.refresh(alert)
            results.append(AlertResponse.model_validate(alert))

        return results

    async def get_active_alerts(self) -> List[AlertResponse]:
        """Get all active alerts."""
        result = await self.db.execute(
            select(SupplyChainAlert)
            .where(SupplyChainAlert.status == "active")
            .order_by(SupplyChainAlert.created_at.desc())
        )
        alerts = result.scalars().all()
        return [AlertResponse.model_validate(a) for a in alerts]

    async def acknowledge_alert(self, alert_id: uuid.UUID) -> Optional[AlertResponse]:
        """Acknowledge an alert."""
        result = await self.db.execute(
            select(SupplyChainAlert).where(SupplyChainAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None
        alert.status = "acknowledged"
        await self.db.flush()
        await self.db.refresh(alert)
        return AlertResponse.model_validate(alert)

    async def resolve_alert(self, alert_id: uuid.UUID) -> Optional[AlertResponse]:
        """Resolve an alert."""
        result = await self.db.execute(
            select(SupplyChainAlert).where(SupplyChainAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(alert)
        return AlertResponse.model_validate(alert)

    def _make_alert(
        self, alert_type: str, severity: str, title: str, description: str, action: str
    ) -> dict:
        return {
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "description": description,
            "suggested_action": action,
            "status": "active",
        }
