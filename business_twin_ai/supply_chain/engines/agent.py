"""Supply Chain Agent engine.

Natural language Q&A about supply chain operations.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.supply_chain.models.database import (
    InventoryItem,
    Shipment,
    Supplier,
    SupplyChainAlert,
    SupplyChainRisk,
    Warehouse,
)
from business_twin_ai.supply_chain.prompts.templates import (
    SC_AGENT_SYSTEM,
    SC_AGENT_USER,
    format_prompt,
)
from business_twin_ai.supply_chain.schemas.schemas import SupplyChainAgentResponse


class SupplyChainAgentEngine:
    """Natural language supply chain assistant."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_client()

    async def ask(self, question: str) -> SupplyChainAgentResponse:
        """Answer a natural language supply chain question."""
        # Gather context
        state = await self._get_supply_chain_state()
        risks = await self._get_active_risks()
        alerts = await self._get_recent_alerts()

        # Try LLM
        prompt = format_prompt(
            SC_AGENT_USER,
            supply_chain_state=str(state),
            active_risks=str(risks),
            recent_alerts=str(alerts),
            question=question,
        )

        try:
            response = await self.llm.chat(SC_AGENT_SYSTEM, prompt)
            return SupplyChainAgentResponse(
                answer=response,
                context_used=state,
                confidence=0.85,
            )
        except Exception:
            return self._rule_based_answer(question, state, risks, alerts)

    def _rule_based_answer(
        self, question: str, state: Dict[str, Any], risks: List, alerts: List
    ) -> SupplyChainAgentResponse:
        """Rule-based answer when LLM is unavailable."""
        q = question.lower()

        if any(w in q for w in ["supplier", "vendor"]):
            answer = (
                f"Supply Chain has {state.get('total_suppliers', 0)} active suppliers. "
                f"Average reliability: {state.get('avg_reliability', 0):.1f}/100. "
                f"{state.get('high_risk_suppliers', 0)} suppliers are high-risk. "
                f"Consider diversifying suppliers with low reliability scores."
            )
        elif any(w in q for w in ["inventory", "stock"]):
            answer = (
                f"Total inventory: {state.get('total_inventory', 0)} units across "
                f"{state.get('total_warehouses', 0)} warehouses. "
                f"{state.get('low_stock_items', 0)} items are below reorder level. "
                f"{state.get('overstock_items', 0)} items are overstocked. "
                f"Review low-stock items for immediate reorder."
            )
        elif any(w in q for w in ["warehouse", "storage"]):
            answer = (
                f"{state.get('total_warehouses', 0)} warehouses operational. "
                f"Average utilization: {state.get('avg_utilization', 0):.1f}%. "
                f"{state.get('overloaded_warehouses', 0)} warehouses are above 90% capacity. "
                f"Consider redistributing inventory to underutilized locations."
            )
        elif any(w in q for w in ["shipment", "delivery", "transport"]):
            answer = (
                f"{state.get('total_shipments', 0)} total shipments. "
                f"{state.get('in_transit', 0)} in transit, {state.get('delayed_shipments', 0)} delayed. "
                f"Total transport cost: ${state.get('total_transport_cost', 0):,.2f}. "
                f"Review delayed shipments and optimize routes."
            )
        elif any(w in q for w in ["risk", "danger", "threat"]):
            answer = (
                f"{len(risks)} active risks detected. "
                f"{state.get('critical_risks', 0)} critical, "
                f"{state.get('high_risks', 0)} high-severity risks. "
                f"Top risks: {', '.join(r['type'] for r in risks[:3]) if risks else 'None'}. "
                f"Focus on mitigating critical risks first."
            )
        elif any(w in q for w in ["cost", "expense"]):
            answer = (
                f"Total transport cost: ${state.get('total_transport_cost', 0):,.2f}. "
                f"Total fuel cost: ${state.get('total_fuel_cost', 0):,.2f}. "
                f"Route optimization could save ~15% on transportation costs. "
                f"Review supplier pricing for cost reduction opportunities."
            )
        elif any(w in q for w in ["reorder", "purchase"]):
            low_items = state.get('low_stock_items', 0)
            answer = (
                f"{low_items} items need reordering. "
                f"Check inventory dashboard for items below reorder level. "
                f"Prioritize critical items and review supplier lead times."
            )
        elif any(w in q for w in ["alert", "notification"]):
            answer = (
                f"{len(alerts)} active alerts. "
                + (f"Latest: {alerts[0]['title']}" if alerts else "No active alerts.") +
                f" Review and acknowledge alerts promptly."
            )
        else:
            answer = (
                f"Supply Chain Overview: {state.get('total_suppliers', 0)} suppliers, "
                f"{state.get('total_warehouses', 0)} warehouses, "
                f"{state.get('total_inventory', 0)} inventory units. "
                f"{len(risks)} active risks, {len(alerts)} alerts. "
                f"Ask specific questions about suppliers, inventory, warehouses, shipments, or risks."
            )

        return SupplyChainAgentResponse(
            answer=answer,
            context_used=state,
            confidence=0.6,
        )

    async def _get_supply_chain_state(self) -> Dict[str, Any]:
        """Get current supply chain state."""
        suppliers = (await self.db.execute(select(Supplier).where(Supplier.is_active == True))).scalars().all()
        warehouses = (await self.db.execute(select(Warehouse).where(Warehouse.is_active == True))).scalars().all()
        inventory = (await self.db.execute(select(InventoryItem))).scalars().all()
        shipments = (await self.db.execute(select(Shipment))).scalars().all()

        avg_reliability = sum(s.reliability_score for s in suppliers) / max(len(suppliers), 1)
        avg_utilization = sum(w.utilization for w in warehouses) / max(len(warehouses), 1)

        return {
            "total_suppliers": len(suppliers),
            "avg_reliability": round(avg_reliability, 1),
            "high_risk_suppliers": len([s for s in suppliers if s.risk_score > 60]),
            "total_warehouses": len(warehouses),
            "avg_utilization": round(avg_utilization, 1),
            "overloaded_warehouses": len([w for w in warehouses if w.utilization > 90]),
            "total_inventory": sum(i.current_stock for i in inventory),
            "low_stock_items": len([i for i in inventory if i.current_stock <= i.reorder_level]),
            "overstock_items": len([i for i in inventory if i.current_stock > i.max_stock * 0.9]),
            "total_shipments": len(shipments),
            "in_transit": len([s for s in shipments if s.status == "in_transit"]),
            "delayed_shipments": len([s for s in shipments if s.status == "delayed"]),
            "total_transport_cost": sum(s.transport_cost for s in shipments),
            "total_fuel_cost": sum(s.fuel_cost for s in shipments),
        }

    async def _get_active_risks(self) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(SupplyChainRisk).where(SupplyChainRisk.status == "active").limit(10)
        )
        return [{"type": r.risk_type, "score": r.risk_score, "severity": r.severity} for r in result.scalars().all()]

    async def _get_recent_alerts(self) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(SupplyChainAlert).where(SupplyChainAlert.status == "active").limit(5)
        )
        return [{"title": a.title, "severity": a.severity} for a in result.scalars().all()]
