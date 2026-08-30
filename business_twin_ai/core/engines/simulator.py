"""Decision Simulator engine.

Processes business decisions and runs them through the prediction,
scenario, confidence, and recommendation engines to produce a full
simulation result.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.models.database import Simulation
from business_twin_ai.core.schemas.schemas import (
    ConfidenceResult,
    DecisionRequest,
    ExplanationResult,
    RecommendationResult,
    ScenarioResult,
)
from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.services.prompts.templates import (
    CONFIDENCE_SYSTEM,
    CONFIDENCE_USER,
    EXPLAINABILITY_SYSTEM,
    EXPLAINABILITY_USER,
    PREDICTION_SYSTEM,
    PREDICTION_USER,
    RECOMMENDATION_SYSTEM,
    RECOMMENDATION_USER,
    SCENARIO_SYSTEM,
    SCENARIO_USER,
    format_prompt,
)

# ── Valid decision types and their default parameters ────────────────────────
VALID_DECISIONS: Dict[str, Dict[str, Any]] = {
    "increase_price": {"default_percent": 10, "description": "Increase product pricing"},
    "reduce_price": {"default_percent": 10, "description": "Reduce product pricing"},
    "open_branch": {"description": "Open a new branch/office"},
    "close_branch": {"description": "Close an existing branch/office"},
    "hire_employees": {"default_count": 10, "description": "Hire new employees"},
    "layoff_employees": {"default_count": 5, "description": "Reduce workforce"},
    "increase_marketing": {"default_percent": 20, "description": "Increase marketing spend"},
    "reduce_marketing": {"default_percent": 20, "description": "Reduce marketing spend"},
    "launch_product": {"description": "Launch a new product"},
    "stop_product": {"description": "Discontinue a product"},
    "enter_new_city": {"description": "Expand to a new city/market"},
    "change_supplier_cost": {"default_percent": 15, "description": "Change supplier costs"},
    "increase_production_capacity": {"default_percent": 25, "description": "Increase production capacity"},
}


class SimulatorEngine:
    """Orchestrates the full simulation pipeline for a business decision."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.twin_engine = DigitalTwinEngine(db)
        self.llm = get_llm_client()

    async def run_simulation(
        self, twin_id: uuid.UUID, request: DecisionRequest
    ) -> Simulation:
        """Run a full simulation for the given decision and return the stored Simulation."""
        # 1. Fetch the twin
        twin = await self.twin_engine.get_twin(twin_id)
        if not twin:
            raise ValueError(f"Digital twin {twin_id} not found")

        if request.decision_type not in VALID_DECISIONS:
            raise ValueError(
                f"Invalid decision type: {request.decision_type}. "
                f"Valid types: {list(VALID_DECISIONS.keys())}"
            )

        twin_state = self.twin_engine.get_twin_state(twin)
        state_json = str(twin_state)
        params_json = str(request.decision_params)

        # 2. Run all AI analysis steps (can be parallelized in production)
        predictions = await self._predict(twin_state, request.decision_type, request.decision_params)
        scenarios = await self._analyze_scenarios(twin_state, request, predictions)
        confidence = await self._assess_confidence(twin_state, request)
        recommendation = await self._generate_recommendation(twin_state, request, predictions, scenarios)
        explanation = await self._explain(twin_state, request, predictions)

        # 3. Extract key prediction values
        pred_data = predictions.get("predictions", {})
        revenue_pred = pred_data.get("revenue", {})
        profit_pred = pred_data.get("profit", {})
        cash_pred = pred_data.get("cash_flow", {})
        customer_pred = pred_data.get("customer_growth", {})
        market_pred = pred_data.get("market_share", {})
        cost_pred = pred_data.get("operational_cost", {})
        roi_pred = pred_data.get("roi", {})
        health_pred = pred_data.get("business_health_score", {})

        # 4. Create simulation record
        sim = Simulation(
            twin_id=twin_id,
            decision_type=request.decision_type,
            decision_params=request.decision_params,
            predicted_revenue=revenue_pred.get("predicted", twin.revenue),
            predicted_profit=profit_pred.get("predicted", twin.profit),
            predicted_cash_flow=cash_pred.get("predicted", twin.cash_flow),
            predicted_customers=customer_pred.get("predicted", twin.customers),
            predicted_market_share=market_pred.get("predicted", twin.market_share),
            predicted_operational_cost=cost_pred.get("predicted", twin.expenses),
            predicted_roi=roi_pred.get("predicted", 0.0),
            predicted_health_score=health_pred.get("predicted", twin.business_health_score),
            predictions=predictions,
            scenarios=[s.model_dump() for s in scenarios],
            confidence_score=confidence.score,
            confidence_level=confidence.level,
            confidence_details=confidence.model_dump(),
            recommendation=recommendation.model_dump(),
            explanation=explanation.model_dump(),
        )

        self.db.add(sim)
        await self.db.flush()
        return sim

    # ── Private AI steps ─────────────────────────────────────────────────────

    async def _predict(
        self, twin_state: Dict[str, Any], decision_type: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run AI prediction for the given decision."""
        prompt = format_prompt(
            PREDICTION_USER,
            business_state=str(twin_state),
            decision_type=decision_type,
            decision_params=str(params),
        )
        try:
            return await self.llm.chat_json(PREDICTION_SYSTEM, prompt)
        except Exception as e:
            # Fallback: rule-based predictions
            return self._rule_based_predictions(twin_state, decision_type, params)

    async def _analyze_scenarios(
        self,
        twin_state: Dict[str, Any],
        request: DecisionRequest,
        predictions: Dict[str, Any],
    ) -> list[ScenarioResult]:
        """Generate best/expected/worst case scenarios."""
        prompt = format_prompt(
            SCENARIO_USER,
            business_state=str(twin_state),
            decision_type=request.decision_type,
            decision_params=str(request.decision_params),
            predictions=str(predictions),
        )
        try:
            data = await self.llm.chat_json(SCENARIO_SYSTEM, prompt)
            scenarios = data.get("scenarios", [])
            if scenarios and len(scenarios) >= 2:
                return [ScenarioResult(**s) for s in scenarios[:3]]
            # Fallback if LLM response doesn't have valid scenarios
            return self._rule_based_scenarios(twin_state, request, predictions)
        except Exception:
            return self._rule_based_scenarios(twin_state, request, predictions)

    async def _assess_confidence(
        self, twin_state: Dict[str, Any], request: DecisionRequest
    ) -> ConfidenceResult:
        """Assess AI confidence in the simulation."""
        # Compute data quality indicators
        has_historical = bool(twin_state.get("kpis"))
        data_completeness = self._calc_completeness(twin_state)
        has_market_data = bool(twin_state.get("competitors"))
        has_trends = bool(twin_state.get("kpis"))
        complexity = len(request.decision_params)

        prompt = format_prompt(
            CONFIDENCE_USER,
            business_state=str(twin_state),
            decision_type=request.decision_type,
            decision_params=str(request.decision_params),
            has_historical=str(has_historical),
            data_completeness=str(data_completeness),
            has_market_data=str(has_market_data),
            has_trends=str(has_trends),
            complexity=str(complexity),
        )
        try:
            data = await self.llm.chat_json(CONFIDENCE_SYSTEM, prompt)
            return ConfidenceResult(**data)
        except Exception:
            return self._rule_based_confidence(data_completeness, has_historical, has_market_data)

    async def _generate_recommendation(
        self,
        twin_state: Dict[str, Any],
        request: DecisionRequest,
        predictions: Dict[str, Any],
        scenarios: list[ScenarioResult],
    ) -> RecommendationResult:
        """Generate an AI recommendation."""
        prompt = format_prompt(
            RECOMMENDATION_USER,
            business_state=str(twin_state),
            decision_type=request.decision_type,
            decision_params=str(request.decision_params),
            predictions=str(predictions),
            scenarios=str([s.model_dump() for s in scenarios]),
        )
        try:
            data = await self.llm.chat_json(RECOMMENDATION_SYSTEM, prompt)
            return RecommendationResult(**data)
        except Exception:
            return self._rule_based_recommendation(request, predictions)

    async def _explain(
        self,
        twin_state: Dict[str, Any],
        request: DecisionRequest,
        predictions: Dict[str, Any],
    ) -> ExplanationResult:
        """Generate explainable AI output."""
        prompt = format_prompt(
            EXPLAINABILITY_USER,
            business_state=str(twin_state),
            decision_type=request.decision_type,
            decision_params=str(request.decision_params),
            predictions=str(predictions),
        )
        try:
            data = await self.llm.chat_json(EXPLAINABILITY_SYSTEM, prompt)
            return ExplanationResult(**data)
        except Exception:
            return self._rule_based_explanation(request)

    # ── Rule-based fallbacks ─────────────────────────────────────────────────

    def _rule_based_predictions(
        self, state: Dict[str, Any], decision_type: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate predictions using business rules when LLM is unavailable."""
        revenue = state.get("revenue", 0)
        profit = state.get("profit", 0)
        customers = state.get("customers", 0)
        expenses = state.get("expenses", 0)

        modifiers = {
            "increase_price": {"revenue": 0.08, "profit": 0.12, "customers": -0.03, "expenses": 0.0},
            "reduce_price": {"revenue": -0.05, "profit": -0.08, "customers": 0.10, "expenses": 0.0},
            "open_branch": {"revenue": 0.15, "profit": -0.05, "customers": 0.20, "expenses": 0.25},
            "close_branch": {"revenue": -0.12, "profit": 0.08, "customers": -0.15, "expenses": -0.20},
            "hire_employees": {"revenue": 0.10, "profit": -0.03, "customers": 0.05, "expenses": 0.08},
            "layoff_employees": {"revenue": -0.05, "profit": 0.10, "customers": -0.02, "expenses": -0.12},
            "increase_marketing": {"revenue": 0.12, "profit": -0.02, "customers": 0.15, "expenses": 0.10},
            "reduce_marketing": {"revenue": -0.08, "profit": 0.05, "customers": -0.10, "expenses": -0.08},
            "launch_product": {"revenue": 0.20, "profit": -0.05, "customers": 0.10, "expenses": 0.15},
            "stop_product": {"revenue": -0.10, "profit": 0.08, "customers": -0.05, "expenses": -0.10},
            "enter_new_city": {"revenue": 0.18, "profit": -0.03, "customers": 0.25, "expenses": 0.20},
            "change_supplier_cost": {"revenue": 0.0, "profit": 0.07, "customers": 0.0, "expenses": -0.10},
            "increase_production_capacity": {"revenue": 0.15, "profit": 0.05, "customers": 0.08, "expenses": 0.12},
        }

        mod = modifiers.get(decision_type, {"revenue": 0, "profit": 0, "customers": 0, "expenses": 0})

        def _pred(current: float, change: float) -> Dict[str, Any]:
            predicted = current * (1 + change)
            pct = change * 100
            return {
                "current": round(current, 2),
                "predicted": round(predicted, 2),
                "change_percent": round(pct, 2),
                "direction": "up" if pct > 0 else ("down" if pct < 0 else "neutral"),
            }

        new_revenue = revenue * (1 + mod["revenue"])
        new_expenses = expenses * (1 + mod["expenses"])
        new_profit = new_revenue - new_expenses

        return {
            "predictions": {
                "revenue": _pred(revenue, mod["revenue"]),
                "profit": _pred(profit, mod["profit"]),
                "cash_flow": _pred(state.get("cash_flow", 0), mod["revenue"] * 0.8),
                "customer_growth": _pred(customers, mod["customers"]),
                "customer_churn": _pred(5.0, -mod["customers"] * 0.5),
                "market_share": _pred(state.get("market_share", 0), mod["revenue"] * 0.3),
                "operational_cost": _pred(expenses, mod["expenses"]),
                "employee_productivity": _pred(
                    state.get("kpis", {}).get("employee_productivity", revenue / max(state.get("employees", 1), 1)),
                    mod["revenue"] * 0.5,
                ),
                "roi": _pred(15.0, mod["profit"] * 2),
                "business_growth": _pred(10.0, mod["revenue"]),
                "expected_sales": _pred(state.get("sales", 0), mod["revenue"]),
                "demand": _pred(100.0, mod["customers"] * 0.8),
                "inventory_usage": _pred(70.0, mod["revenue"] * 0.4),
                "brand_value": _pred(50.0, mod["revenue"] * 0.3),
                "business_health_score": _pred(state.get("business_health_score", 50), mod["profit"] * 0.5),
            }
        }

    def _rule_based_scenarios(
        self,
        state: Dict[str, Any],
        request: DecisionRequest,
        predictions: Dict[str, Any],
    ) -> list[ScenarioResult]:
        """Generate rule-based scenarios."""
        pred = predictions.get("predictions", {})
        base_rev = pred.get("revenue", {}).get("predicted", state.get("revenue", 0))
        base_profit = pred.get("profit", {}).get("predicted", state.get("profit", 0))

        return [
            ScenarioResult(
                label="Best Case",
                revenue=round(base_rev * 1.15, 2),
                profit=round(base_profit * 1.20, 2),
                roi=round(25.0, 2),
                demand=round(120.0, 2),
                risk=round(20.0, 2),
                probability=round(25.0, 2),
                explanation="Market conditions are favorable and the decision amplifies existing strengths.",
            ),
            ScenarioResult(
                label="Expected Case",
                revenue=round(base_rev, 2),
                profit=round(base_profit, 2),
                roi=round(18.0, 2),
                demand=round(100.0, 2),
                risk=round(40.0, 2),
                probability=round(55.0, 2),
                explanation="Moderate impact with balanced risk and market conditions.",
            ),
            ScenarioResult(
                label="Worst Case",
                revenue=round(base_rev * 0.85, 2),
                profit=round(base_profit * 0.70, 2),
                roi=round(8.0, 2),
                demand=round(75.0, 2),
                risk=round(70.0, 2),
                probability=round(20.0, 2),
                explanation="Adverse market conditions or execution challenges reduce expected outcomes.",
            ),
        ]

    def _rule_based_confidence(
        self, completeness: float, has_historical: bool, has_market: bool
    ) -> ConfidenceResult:
        """Rule-based confidence assessment."""
        score = 50.0
        factors = []

        if completeness > 80:
            score += 20
            factors.append("High data completeness")
        elif completeness > 50:
            score += 10
            factors.append("Moderate data completeness")
        else:
            score -= 10
            factors.append("Low data completeness")

        if has_historical:
            score += 15
            factors.append("Historical KPI data available")

        if has_market:
            score += 10
            factors.append("Market/competitor data available")

        score = max(0, min(100, score))

        if score >= 75:
            level = "High"
        elif score >= 50:
            level = "Medium"
        else:
            level = "Low"

        return ConfidenceResult(
            score=round(score, 1),
            level=level,
            reason=f"Confidence is {level.lower()} based on data completeness ({completeness:.0f}%) and available market data.",
            supporting_factors=factors,
        )

    def _rule_based_recommendation(
        self, request: DecisionRequest, predictions: Dict[str, Any]
    ) -> RecommendationResult:
        """Rule-based recommendation."""
        pred = predictions.get("predictions", {})
        profit_change = pred.get("profit", {}).get("change_percent", 0)
        revenue_change = pred.get("revenue", {}).get("change_percent", 0)

        if profit_change > 5:
            rec = f"Proceed with {request.decision_type.replace('_', ' ')} — strong positive profit impact expected."
        elif profit_change > 0:
            rec = f"Consider a more moderate version of {request.decision_type.replace('_', ' ')} for better ROI."
        else:
            rec = f"Reconsider {request.decision_type.replace('_', ' ')} — negative profit impact detected. Explore alternatives."

        return RecommendationResult(
            recommendation=rec,
            expected_improvement=f"Revenue: {revenue_change:+.1f}%, Profit: {profit_change:+.1f}%",
            reasoning=f"Based on projected metrics, this decision impacts revenue by {revenue_change:+.1f}% and profit by {profit_change:+.1f}%.",
            business_impact="Moderate operational and financial impact expected.",
            alternative_strategy="Consider a phased approach or pilot program before full implementation.",
        )

    def _rule_based_explanation(self, request: DecisionRequest) -> ExplanationResult:
        """Rule-based explanation."""
        return ExplanationResult(
            why=f"The {request.decision_type.replace('_', ' ')} decision was analyzed based on current business metrics and market assumptions.",
            factors=["Revenue trends", "Cost structure", "Market position", "Customer base"],
            positive_factors=["Revenue growth potential", "Market demand"],
            negative_factors=["Implementation costs", "Transition risks"],
            assumptions=["Market conditions remain stable", "No major competitor response"],
            limitations=["Does not account for black swan events", "Based on current data snapshot"],
        )

    def _calc_completeness(self, state: Dict[str, Any]) -> float:
        """Calculate data completeness percentage."""
        key_fields = [
            "revenue", "expenses", "customers", "employees", "products",
            "sales", "marketing_budget", "pricing", "competitors", "kpis",
        ]
        filled = sum(1 for f in key_fields if state.get(f))
        return round((filled / len(key_fields)) * 100, 1)
