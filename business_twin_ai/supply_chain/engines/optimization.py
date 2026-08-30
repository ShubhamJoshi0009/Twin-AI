"""Supply Chain Optimization Engine.

Recommends actions to reduce costs and improve efficiency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.supply_chain.models.database import (
    InventoryItem,
    Shipment,
    Supplier,
    Warehouse,
)
from business_twin_ai.supply_chain.prompts.templates import (
    SC_OPTIMIZATION_SYSTEM,
    SC_OPTIMIZATION_USER,
    format_prompt,
)
from business_twin_ai.supply_chain.schemas.schemas import (
    OptimizationRecommendation,
    OptimizationResponse,
)


class OptimizationEngine:
    """Analyzes and optimizes the entire supply chain."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_client()

    async def optimize(self) -> OptimizationResponse:
        """Run full supply chain optimization."""
        state = await self._get_state()

        try:
            return await self._llm_optimize(state)
        except Exception:
            return self._rule_based_optimize(state)

    async def _get_state(self) -> Dict[str, Any]:
        """Gather supply chain state for optimization."""
        suppliers = (await self.db.execute(select(Supplier).where(Supplier.is_active == True))).scalars().all()
        warehouses = (await self.db.execute(select(Warehouse).where(Warehouse.is_active == True))).scalars().all()
        inventory = (await self.db.execute(select(InventoryItem))).scalars().all()
        shipments = (await self.db.execute(select(Shipment))).scalars().all()

        return {
            "suppliers": suppliers,
            "warehouses": warehouses,
            "inventory": inventory,
            "shipments": shipments,
            "total_transport_cost": sum(s.transport_cost for s in shipments),
            "total_fuel_cost": sum(s.fuel_cost for s in shipments),
            "avg_utilization": sum(w.utilization for w in warehouses) / max(len(warehouses), 1),
            "low_stock_count": len([i for i in inventory if i.current_stock <= i.reorder_level]),
            "overstock_count": len([i for i in inventory if i.current_stock > i.max_stock * 0.9]),
            "delayed_shipments": len([s for s in shipments if s.status == "delayed"]),
            "avg_supplier_reliability": sum(s.reliability_score for s in suppliers) / max(len(suppliers), 1),
        }

    async def _llm_optimize(self, state: Dict[str, Any]) -> OptimizationResponse:
        """LLM-based optimization."""
        state_summary = {
            "total_transport_cost": state["total_transport_cost"],
            "avg_utilization": state["avg_utilization"],
            "low_stock_count": state["low_stock_count"],
            "overstock_count": state["overstock_count"],
            "delayed_shipments": state["delayed_shipments"],
            "avg_supplier_reliability": state["avg_supplier_reliability"],
        }

        prompt = format_prompt(
            SC_OPTIMIZATION_USER,
            supply_chain_state=str(state_summary),
            cost_analysis=f"Transport: ${state['total_transport_cost']:,.2f}, Fuel: ${state['total_fuel_cost']:,.2f}",
            performance_metrics=f"Utilization: {state['avg_utilization']:.1f}%, Reliability: {state['avg_supplier_reliability']:.1f}",
        )
        data = await self.llm.chat_json(SC_OPTIMIZATION_SYSTEM, prompt)

        recs = [OptimizationRecommendation(**r) for r in data.get("recommendations", [])]
        return OptimizationResponse(
            recommendations=recs,
            total_potential_saving=data.get("total_potential_saving", 0),
            efficiency_improvement=data.get("efficiency_improvement", 0),
            generated_at=datetime.now(timezone.utc),
        )

    def _rule_based_optimize(self, state: Dict[str, Any]) -> OptimizationResponse:
        """Rule-based optimization."""
        recs: List[OptimizationRecommendation] = []
        total_saving = 0.0

        # Logistics optimization
        if state["delayed_shipments"] > 0:
            saving = state["total_transport_cost"] * 0.15
            total_saving += saving
            recs.append(OptimizationRecommendation(
                category="logistics",
                title="Optimize Delivery Routes",
                description=f"{state['delayed_shipments']} delayed shipments detected. Route optimization can reduce delays and costs.",
                expected_saving=round(saving, 2),
                priority="high",
                implementation_effort="medium",
            ))

        # Supplier optimization
        if state["avg_supplier_reliability"] < 70:
            recs.append(OptimizationRecommendation(
                category="supplier",
                title="Improve Supplier Performance",
                description=f"Average supplier reliability is {state['avg_supplier_reliability']:.1f}/100. Consider performance improvement programs.",
                expected_saving=state["total_transport_cost"] * 0.08,
                priority="high",
                implementation_effort="high",
            ))
            total_saving += state["total_transport_cost"] * 0.08

        # Warehouse optimization
        if state["avg_utilization"] < 50:
            saving = state["avg_utilization"] * 100
            total_saving += saving
            recs.append(OptimizationRecommendation(
                category="warehouse",
                title="Improve Warehouse Utilization",
                description=f"Average warehouse utilization is {state['avg_utilization']:.1f}%. Consolidate inventory to reduce costs.",
                expected_saving=round(saving, 2),
                priority="medium",
                implementation_effort="medium",
            ))

        # Inventory optimization
        if state["overstock_count"] > 0:
            recs.append(OptimizationRecommendation(
                category="inventory",
                title="Reduce Overstock",
                description=f"{state['overstock_count']} items are overstocked. Implement demand-based inventory allocation.",
                expected_saving=state["overstock_count"] * 50,
                priority="medium",
                implementation_effort="low",
            ))
            total_saving += state["overstock_count"] * 50

        if state["low_stock_count"] > 0:
            recs.append(OptimizationRecommendation(
                category="inventory",
                title="Optimize Reorder Levels",
                description=f"{state['low_stock_count']} items below reorder level. Implement automated reorder triggers.",
                expected_saving=state["low_stock_count"] * 25,
                priority="high",
                implementation_effort="low",
            ))
            total_saving += state["low_stock_count"] * 25

        # Procurement optimization
        recs.append(OptimizationRecommendation(
            category="procurement",
            title="Consolidate Procurement",
            description="Consolidate orders across suppliers for volume discounts and reduced administrative costs.",
            expected_saving=state["total_transport_cost"] * 0.05,
            priority="medium",
            implementation_effort="medium",
        ))
        total_saving += state["total_transport_cost"] * 0.05

        return OptimizationResponse(
            recommendations=recs,
            total_potential_saving=round(total_saving, 2),
            efficiency_improvement=round(min(30, len(recs) * 5), 1),
            generated_at=datetime.now(timezone.utc),
        )
