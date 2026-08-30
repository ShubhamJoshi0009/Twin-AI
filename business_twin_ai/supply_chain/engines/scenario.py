"""Supply Chain Scenario Analysis engine.

Simulates disruptive events and predicts their impact.
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.supply_chain.models.database import SupplyChainScenario
from business_twin_ai.supply_chain.prompts.templates import (
    SC_SCENARIO_SYSTEM,
    SC_SCENARIO_USER,
    format_prompt,
)
from business_twin_ai.supply_chain.schemas.schemas import (
    ScenarioImpact,
    ScenarioRequest,
    ScenarioResponse,
)

# Scenario templates with rule-based impacts
SCENARIO_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "supplier_failure": {
        "name": "Supplier Failure",
        "impact_template": {
            "inventory_impact": "Inventory levels will drop as supplier cannot fulfill orders",
            "delivery_impact": "Delivery delays of 2-4 weeks expected",
            "revenue_impact": "Revenue loss of 15-25% in affected product lines",
            "operations_impact": "Production slowdown, need alternative sourcing",
            "lead_time_impact": "Lead time increase of 14-28 days",
            "risk_score_change": 25.0,
            "severity": "high",
        },
        "recommendations": [
            "Immediately activate backup suppliers",
            "Place emergency orders with alternative suppliers",
            "Communicate with affected customers",
            "Review supplier dependency risk",
        ],
    },
    "warehouse_closure": {
        "name": "Warehouse Closure",
        "impact_template": {
            "inventory_impact": "Loss of all inventory at closed warehouse",
            "delivery_impact": "Delivery disruptions for 2-3 weeks",
            "revenue_impact": "Revenue impact depends on warehouse role",
            "operations_impact": "Need to redistribute inventory to other warehouses",
            "lead_time_impact": "Lead time increase of 7-14 days",
            "risk_score_change": 20.0,
            "severity": "high",
        },
        "recommendations": [
            "Activate overflow warehouse capacity",
            "Redistribute inventory to nearest warehouses",
            "Update delivery routes",
            "Assess insurance coverage",
        ],
    },
    "demand_increase": {
        "name": "Demand Spike",
        "impact_template": {
            "inventory_impact": "Inventory depletion accelerated, stockout risk",
            "delivery_impact": "Increased shipment volume, potential delays",
            "revenue_impact": "Revenue increase opportunity if supply chain can scale",
            "operations_impact": "Need to increase production and procurement",
            "lead_time_impact": "Effective lead time reduction needed",
            "risk_score_change": 10.0,
            "severity": "medium",
        },
        "recommendations": [
            "Increase safety stock levels",
            "Place advance orders with suppliers",
            "Expedite pending shipments",
            "Consider temporary warehouse space",
        ],
    },
    "fuel_price_increase": {
        "name": "Fuel Price Increase",
        "impact_template": {
            "inventory_impact": "Minimal direct impact",
            "delivery_impact": "Increased transportation costs, potential route changes",
            "revenue_impact": "Margin compression from higher logistics costs",
            "operations_impact": "Need to optimize routes and consolidate shipments",
            "lead_time_impact": "Slight increase due to route optimization",
            "risk_score_change": 8.0,
            "severity": "medium",
        },
        "recommendations": [
            "Optimize delivery routes to reduce fuel consumption",
            "Consolidate shipments to improve efficiency",
            "Negotiate fuel surcharge caps with carriers",
            "Consider alternative transportation modes",
        ],
    },
    "transportation_strike": {
        "name": "Transportation Strike",
        "impact_template": {
            "inventory_impact": "Severe inventory disruption, potential stockouts",
            "delivery_impact": "Complete delivery stoppage in affected region",
            "revenue_impact": "Significant revenue loss if prolonged",
            "operations_impact": "Need alternative transportation modes",
            "lead_time_impact": "Lead time increase of 7-21 days",
            "risk_score_change": 30.0,
            "severity": "critical",
        },
        "recommendations": [
            "Activate alternative transportation providers",
            "Pre-position inventory at key locations",
            "Communicate proactively with customers",
            "Monitor strike developments closely",
        ],
    },
    "inventory_shortage": {
        "name": "Inventory Shortage",
        "impact_template": {
            "inventory_impact": "Critical stockout across multiple products",
            "delivery_impact": "Fulfillment delays, order backlogs",
            "revenue_impact": "Direct revenue loss from unfulfilled orders",
            "operations_impact": "Need emergency procurement and allocation",
            "lead_time_impact": "Lead time increase of 14-30 days",
            "risk_score_change": 20.0,
            "severity": "high",
        },
        "recommendations": [
            "Place emergency orders with all available suppliers",
            "Implement order allocation prioritization",
            "Communicate delays to affected customers",
            "Review and increase safety stock levels",
        ],
    },
}


class ScenarioEngine:
    """Simulates supply chain scenarios."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_client()

    async def simulate_scenario(self, request: ScenarioRequest) -> ScenarioResponse:
        """Run a scenario simulation."""
        template = SCENARIO_TEMPLATES.get(request.scenario_type)
        if not template:
            raise ValueError(
                f"Unknown scenario type: {request.scenario_type}. "
                f"Valid types: {list(SCENARIO_TEMPLATES.keys())}"
            )

        # Try LLM-enhanced simulation
        try:
            return await self._llm_simulate(request, template)
        except Exception:
            return await self._rule_based_simulate(request, template)

    async def _llm_simulate(
        self, request: ScenarioRequest, template: Dict[str, Any]
    ) -> ScenarioResponse:
        """LLM-enhanced scenario simulation."""
        prompt = format_prompt(
            SC_SCENARIO_USER,
            scenario_type=request.scenario_type,
            scenario_parameters=str(request.parameters),
            supply_chain_state="Current supply chain data available",
        )
        data = await self.llm.chat_json(SC_SCENARIO_SYSTEM, prompt)

        # Persist scenario
        scenario = SupplyChainScenario(
            scenario_type=request.scenario_type,
            name=template["name"],
            parameters=request.parameters,
            impact=data.get("impact", {}),
            recommendations=data.get("recommendations", []),
        )
        self.db.add(scenario)
        await self.db.flush()
        await self.db.refresh(scenario)

        return ScenarioResponse(
            id=scenario.id,
            scenario_type=scenario.scenario_type,
            name=scenario.name,
            impact=ScenarioImpact(**data.get("impact", template["impact_template"])),
            recommendations=data.get("recommendations", template["recommendations"]),
            created_at=scenario.created_at,
        )

    async def _rule_based_simulate(
        self, request: ScenarioRequest, template: Dict[str, Any]
    ) -> ScenarioResponse:
        """Rule-based scenario simulation."""
        impact_data = template["impact_template"].copy()

        # Adjust based on parameters
        severity_multiplier = request.parameters.get("severity_multiplier", 1.0)
        impact_data["risk_score_change"] = round(impact_data["risk_score_change"] * severity_multiplier, 1)

        scenario = SupplyChainScenario(
            scenario_type=request.scenario_type,
            name=template["name"],
            parameters=request.parameters,
            impact=impact_data,
            recommendations=template["recommendations"],
        )
        self.db.add(scenario)
        await self.db.flush()
        await self.db.refresh(scenario)

        return ScenarioResponse(
            id=scenario.id,
            scenario_type=scenario.scenario_type,
            name=scenario.name,
            impact=ScenarioImpact(**impact_data),
            recommendations=template["recommendations"],
            created_at=scenario.created_at,
        )
