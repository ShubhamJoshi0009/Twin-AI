"""Supply Chain Health Score engine.

Calculates overall supply chain health across 8 dimensions.
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.supply_chain.models.database import (
    InventoryItem,
    Shipment,
    Supplier,
    SupplyChainRisk,
    Warehouse,
)
from business_twin_ai.supply_chain.prompts.templates import (
    SC_HEALTH_SYSTEM,
    SC_HEALTH_USER,
    format_prompt,
)
from business_twin_ai.supply_chain.schemas.schemas import SupplyChainHealthResponse


class SupplyChainHealthEngine:
    """Calculates supply chain health scores."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_client()

    async def calculate_health(self) -> SupplyChainHealthResponse:
        """Calculate the full supply chain health score."""
        state = await self._get_state()

        try:
            prompt = format_prompt(SC_HEALTH_USER, supply_chain_state=str(state))
            data = await self.llm.chat_json(SC_HEALTH_SYSTEM, prompt)
            return SupplyChainHealthResponse(**data)
        except Exception:
            return self._rule_based_health(state)

    async def _get_state(self) -> Dict[str, Any]:
        """Gather state for health calculation."""
        suppliers = (await self.db.execute(select(Supplier).where(Supplier.is_active == True))).scalars().all()
        warehouses = (await self.db.execute(select(Warehouse).where(Warehouse.is_active == True))).scalars().all()
        inventory = (await self.db.execute(select(InventoryItem))).scalars().all()
        shipments = (await self.db.execute(select(Shipment))).scalars().all()
        risks = (await self.db.execute(
            select(SupplyChainRisk).where(SupplyChainRisk.status == "active")
        )).scalars().all()

        return {
            "suppliers": suppliers,
            "warehouses": warehouses,
            "inventory": inventory,
            "shipments": shipments,
            "risks": risks,
            "avg_reliability": sum(s.reliability_score for s in suppliers) / max(len(suppliers), 1),
            "avg_quality": sum(s.quality_rating for s in suppliers) / max(len(suppliers), 1),
            "avg_utilization": sum(w.utilization for w in warehouses) / max(len(warehouses), 1),
            "total_inventory": sum(i.current_stock for i in inventory),
            "low_stock_count": len([i for i in inventory if i.current_stock <= i.reorder_level]),
            "overstock_count": len([i for i in inventory if i.current_stock > i.max_stock * 0.9]),
            "total_shipments": len(shipments),
            "on_time_deliveries": len([s for s in shipments if s.status == "delivered"]),
            "delayed_shipments": len([s for s in shipments if s.status == "delayed"]),
            "total_transport_cost": sum(s.transport_cost for s in shipments),
            "active_risks": len(risks),
            "critical_risks": len([r for r in risks if r.severity == "critical"]),
        }

    def _rule_based_health(self, state: Dict[str, Any]) -> SupplyChainHealthResponse:
        """Calculate health using business rules."""
        scores: Dict[str, float] = {}

        # Supplier Performance (0-100)
        scores["supplier_performance"] = min(100, max(0, state["avg_reliability"]))

        # Inventory Health (0-100)
        total_items = len(state["inventory"]) or 1
        low_pct = state["low_stock_count"] / total_items * 100
        over_pct = state["overstock_count"] / total_items * 100
        scores["inventory_health"] = min(100, max(0, 100 - low_pct * 2 - over_pct))

        # Warehouse Efficiency (0-100)
        scores["warehouse_efficiency"] = min(100, max(0, 100 - abs(state["avg_utilization"] - 70) * 2))

        # Transportation (0-100)
        total_shipments = state["total_shipments"] or 1
        delayed_pct = state["delayed_shipments"] / total_shipments * 100
        scores["transportation"] = min(100, max(0, 100 - delayed_pct * 3))

        # Delivery Performance (0-100)
        on_time = state["on_time_deliveries"]
        scores["delivery_performance"] = min(100, max(0, (on_time / total_shipments * 100) if total_shipments > 0 else 75))

        # Demand Fulfillment (0-100)
        scores["demand_fulfillment"] = min(100, max(0, 100 - low_pct * 2))

        # Risk Level (0-100, inverted: lower risk = higher score)
        risk_penalty = state["critical_risks"] * 20 + state["active_risks"] * 5
        scores["risk_level"] = min(100, max(0, 100 - risk_penalty))

        # Cost Efficiency (0-100)
        avg_cost = state["total_transport_cost"] / max(total_shipments, 1)
        scores["cost_efficiency"] = min(100, max(0, 100 - (avg_cost - 100) * 0.5))

        overall = sum(scores.values()) / len(scores)

        # Trend
        if state["delayed_shipments"] == 0 and state["low_stock_count"] == 0:
            trend = "improving"
        elif state["critical_risks"] > 2 or state["delayed_shipments"] > 3:
            trend = "declining"
        else:
            trend = "stable"

        # Suggestions
        suggestions = []
        if scores["supplier_performance"] < 60:
            suggestions.append("Improve supplier performance through regular reviews and scorecards.")
        if scores["inventory_health"] < 60:
            suggestions.append("Optimize inventory levels — address low stock and overstock items.")
        if scores["warehouse_efficiency"] < 60:
            suggestions.append("Improve warehouse utilization through better space management.")
        if scores["transportation"] < 60:
            suggestions.append("Optimize delivery routes and address delayed shipments.")
        if scores["risk_level"] < 60:
            suggestions.append("Implement risk mitigation strategies for critical risks.")
        if scores["cost_efficiency"] < 60:
            suggestions.append("Review and negotiate logistics costs with carriers.")
        if not suggestions:
            suggestions.append("Supply chain is healthy. Focus on continuous improvement.")

        return SupplyChainHealthResponse(
            overall_score=round(overall, 1),
            category_scores={k: round(v, 1) for k, v in scores.items()},
            trend=trend,
            suggestions=suggestions,
        )
