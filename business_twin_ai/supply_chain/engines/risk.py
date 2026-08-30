"""Supply Chain Risk Detection and Prediction engine.

Detects and predicts supply chain risks with scoring and prioritization.
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
    SupplyChainRisk,
    Warehouse,
)
from business_twin_ai.supply_chain.prompts.templates import (
    SC_RISK_PREDICTION_SYSTEM,
    SC_RISK_PREDICTION_USER,
    format_prompt,
)
from business_twin_ai.supply_chain.schemas.schemas import (
    RiskPrediction,
    RiskPredictionResponse,
    RiskResponse,
)


class RiskEngine:
    """Detects and predicts supply chain risks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_client()

    async def detect_risks(self) -> List[RiskResponse]:
        """Scan the supply chain and detect all active risks."""
        # Gather data
        suppliers = await self._get_all_suppliers()
        warehouses = await self._get_all_warehouses()
        shipments = await self._get_all_shipments()
        inventory = await self._get_all_inventory()

        risks: List[Dict[str, Any]] = []

        # Supplier risks
        for s in suppliers:
            if s.reliability_score < 60:
                risks.append(self._make_risk(
                    "supplier_failure", f"Low Reliability: {s.name}",
                    f"Supplier {s.name} has reliability score of {s.reliability_score}/100.",
                    "high", 70, s.id, "supplier",
                ))
            if s.risk_score > 60:
                risks.append(self._make_risk(
                    "supplier_delay", f"High Risk Supplier: {s.name}",
                    f"Supplier {s.name} has risk score of {s.risk_score}/100.",
                    "medium", 55, s.id, "supplier",
                ))

        # Inventory risks
        for item in inventory:
            available = item.current_stock - item.reserved_stock
            if available <= 0:
                risks.append(self._make_risk(
                    "inventory_shortage", f"Stockout: {item.product_name}",
                    f"{item.product_name} is out of stock at warehouse.",
                    "critical", 90, str(item.id), "inventory",
                ))
            elif available <= item.safety_stock:
                risks.append(self._make_risk(
                    "inventory_shortage", f"Low Stock: {item.product_name}",
                    f"{item.product_name} below safety stock level ({available} units).",
                    "high", 75, str(item.id), "inventory",
                ))
            if item.current_stock > item.max_stock * 0.9:
                risks.append(self._make_risk(
                    "overstock", f"Overstock: {item.product_name}",
                    f"{item.product_name} at {item.current_stock}/{item.max_stock} capacity.",
                    "medium", 45, str(item.id), "inventory",
                ))

        # Warehouse risks
        for w in warehouses:
            if w.utilization > 90:
                risks.append(self._make_risk(
                    "warehouse_capacity", f"Warehouse Overloaded: {w.name}",
                    f"Warehouse {w.name} at {w.utilization:.0f}% capacity.",
                    "high", 70, str(w.id), "warehouse",
                ))

        # Shipment risks
        for s in shipments:
            if s.status == "delayed":
                risks.append(self._make_risk(
                    "transportation_delay", f"Delayed Shipment: {s.shipment_number}",
                    f"Shipment {s.shipment_number} is delayed.",
                    "medium", 60, str(s.id), "shipment",
                ))

        # Persist and return
        results = []
        for risk_data in risks:
            risk = SupplyChainRisk(**risk_data)
            self.db.add(risk)
            await self.db.flush()
            await self.db.refresh(risk)
            results.append(RiskResponse.model_validate(risk))

        return results

    async def get_active_risks(self) -> List[RiskResponse]:
        """Get all active risks."""
        result = await self.db.execute(
            select(SupplyChainRisk)
            .where(SupplyChainRisk.status == "active")
            .order_by(SupplyChainRisk.risk_score.desc())
        )
        risks = result.scalars().all()
        return [RiskResponse.model_validate(r) for r in risks]

    async def predict_risks(self) -> RiskPredictionResponse:
        """Predict future risks using AI."""
        # Gather context
        suppliers = await self._get_all_suppliers()
        shipments = await self._get_all_shipments()
        inventory = await self._get_all_inventory()
        active_risks = await self.get_active_risks()

        state = {
            "suppliers": len(suppliers),
            "avg_reliability": sum(s.reliability_score for s in suppliers) / max(len(suppliers), 1),
            "delayed_shipments": len([s for s in shipments if s.status == "delayed"]),
            "total_inventory": sum(i.current_stock for i in inventory),
            "low_stock_items": len([i for i in inventory if i.current_stock <= i.reorder_level]),
            "active_risks": len(active_risks),
        }

        try:
            return await self._llm_predict(state, active_risks)
        except Exception:
            return self._rule_based_predict(state)

    async def _llm_predict(
        self, state: Dict[str, Any], active_risks: List[RiskResponse]
    ) -> RiskPredictionResponse:
        """LLM-based risk prediction."""
        risks_data = [{"type": r.risk_type, "score": r.risk_score, "severity": r.severity} for r in active_risks[:10]]

        prompt = format_prompt(
            SC_RISK_PREDICTION_USER,
            supply_chain_state=str(state),
            historical_risks="Historical risk data available",
            active_risks=str(risks_data),
        )
        data = await self.llm.chat_json(SC_RISK_PREDICTION_SYSTEM, prompt)
        predictions = [RiskPrediction(**p) for p in data.get("predictions", [])]
        return RiskPredictionResponse(
            predictions=predictions,
            overall_risk_level=data.get("overall_risk_level", "medium"),
            generated_at=datetime.now(timezone.utc),
        )

    def _rule_based_predict(self, state: Dict[str, Any]) -> RiskPredictionResponse:
        """Rule-based risk prediction."""
        predictions = []
        avg_reliability = state.get("avg_reliability", 70)

        # Supplier failure risk
        supplier_fail_prob = max(0, min(100, 100 - avg_reliability))
        predictions.append(RiskPrediction(
            risk_type="supplier_failure", probability=round(supplier_fail_prob, 1),
            confidence=75.0, timeframe="30 days",
            factors=["Low average reliability", "Historical performance"],
            mitigation="Diversify supplier base",
        ))

        # Delivery delay risk
        delayed = state.get("delayed_shipments", 0)
        delay_prob = min(100, delayed * 15 + 20)
        predictions.append(RiskPrediction(
            risk_type="delivery_delay", probability=round(delay_prob, 1),
            confidence=80.0, timeframe="30 days",
            factors=[f"{delayed} delayed shipments", "Route conditions"],
            mitigation="Optimize routes and add buffer time",
        ))

        # Inventory shortage
        low_stock = state.get("low_stock_items", 0)
        shortage_prob = min(100, low_stock * 10 + 15)
        predictions.append(RiskPrediction(
            risk_type="inventory_shortage", probability=round(shortage_prob, 1),
            confidence=85.0, timeframe="30 days",
            factors=[f"{low_stock} items below reorder level", "Demand patterns"],
            mitigation="Increase safety stock levels",
        ))

        # Stockout risk
        predictions.append(RiskPrediction(
            risk_type="stockout", probability=round(shortage_prob * 0.8, 1),
            confidence=70.0, timeframe="60 days",
            factors=["Current inventory levels", "Lead times"],
            mitigation="Place advance orders",
        ))

        # Overall risk level
        avg_prob = sum(p.probability for p in predictions) / len(predictions)
        if avg_prob > 70:
            level = "critical"
        elif avg_prob > 50:
            level = "high"
        elif avg_prob > 30:
            level = "medium"
        else:
            level = "low"

        return RiskPredictionResponse(
            predictions=predictions,
            overall_risk_level=level,
            generated_at=datetime.now(timezone.utc),
        )

    def _make_risk(
        self, risk_type: str, title: str, description: str,
        severity: str, score: float, entity_id: str, entity_type: str,
    ) -> Dict[str, Any]:
        """Create a risk data dictionary."""
        return {
            "risk_type": risk_type,
            "title": title,
            "description": description,
            "severity": severity,
            "probability": score,
            "risk_score": score,
            "business_impact": f"Potential {severity} impact on {entity_type} operations",
            "priority": severity,
            "affected_entity_type": entity_type,
            "affected_entity_id": entity_id,
            "status": "active",
        }

    async def _get_all_suppliers(self) -> List[Supplier]:
        result = await self.db.execute(select(Supplier).where(Supplier.is_active == True))
        return list(result.scalars().all())

    async def _get_all_warehouses(self) -> List[Warehouse]:
        result = await self.db.execute(select(Warehouse).where(Warehouse.is_active == True))
        return list(result.scalars().all())

    async def _get_all_shipments(self) -> List[Shipment]:
        result = await self.db.execute(select(Shipment))
        return list(result.scalars().all())

    async def _get_all_inventory(self) -> List[InventoryItem]:
        result = await self.db.execute(select(InventoryItem))
        return list(result.scalars().all())
