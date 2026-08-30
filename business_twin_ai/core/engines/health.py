"""Business Health Score engine.

Calculates a comprehensive health score across 8 business dimensions:
Finance, Operations, Sales, Customers, Growth, Cash Flow, Inventory, Marketing.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.schemas.schemas import HealthScoreResponse
from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.services.prompts.templates import HEALTH_SYSTEM, HEALTH_USER, format_prompt


class HealthEngine:
    """Calculates business health scores with LLM enhancement."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.twin_engine = DigitalTwinEngine(db)
        self.llm = get_llm_client()

    async def calculate_health(self, twin_id: uuid.UUID) -> HealthScoreResponse:
        """Calculate the full business health score for a twin."""
        twin = await self.twin_engine.get_twin(twin_id)
        if not twin:
            raise ValueError(f"Digital twin {twin_id} not found")

        state = self.twin_engine.get_twin_state(twin)

        # Try LLM-enhanced scoring
        try:
            prompt = format_prompt(HEALTH_USER, business_state=str(state))
            data = await self.llm.chat_json(HEALTH_SYSTEM, prompt)
            return HealthScoreResponse(**data)
        except Exception:
            # Fallback to rule-based scoring
            return self._rule_based_health(state)

    def _rule_based_health(self, state: Dict[str, Any]) -> HealthScoreResponse:
        """Calculate health using business rules."""
        revenue = state.get("revenue", 0)
        expenses = state.get("expenses", 0)
        profit = state.get("profit", 0)
        cash_flow = state.get("cash_flow", 0)
        customers = state.get("customers", 0)
        employees = state.get("employees", 0)
        sales = state.get("sales", 0)
        marketing = state.get("marketing_budget", 0)
        market_share = state.get("market_share", 0)

        # ── Category Scores (0-100) ──────────────────────────
        scores: Dict[str, float] = {}

        # Finance: profit margin, revenue adequacy
        profit_margin = (profit / revenue * 100) if revenue > 0 else 0
        scores["finance"] = min(100, max(0, 50 + profit_margin * 2))

        # Operations: employee productivity
        rev_per_emp = revenue / employees if employees > 0 else 0
        scores["operations"] = min(100, max(0, min(100, rev_per_emp / 200)))

        # Sales: sales vs revenue ratio
        sales_ratio = (sales / revenue * 100) if revenue > 0 else 0
        scores["sales"] = min(100, max(0, sales_ratio))

        # Customers: customer count relative to employees
        cust_ratio = customers / employees if employees > 0 else 0
        scores["customers"] = min(100, max(0, cust_ratio * 5))

        # Growth: market share and positive profit
        scores["growth"] = min(100, max(0, market_share * 3 + (20 if profit > 0 else 0)))

        # Cash Flow: positive cash flow
        cf_ratio = (cash_flow / revenue * 100) if revenue > 0 else 0
        scores["cash_flow"] = min(100, max(0, 50 + cf_ratio))

        # Inventory: assume healthy if products exist
        products = state.get("products", {})
        scores["inventory"] = min(100, max(30, 50 + len(products) * 5))

        # Marketing: ROI
        mktg_roi = (sales / marketing) if marketing > 0 else 0
        scores["marketing"] = min(100, max(0, mktg_roi * 20))

        # Overall score
        overall = sum(scores.values()) / len(scores)

        # Trend determination
        if profit > 0 and cash_flow > 0:
            trend = "improving"
        elif profit < 0 or cash_flow < 0:
            trend = "declining"
        else:
            trend = "stable"

        # Improvement suggestions
        suggestions = []
        if scores["finance"] < 50:
            suggestions.append("Focus on improving profit margins through cost optimization or pricing strategy.")
        if scores["marketing"] < 50:
            suggestions.append("Review marketing spend efficiency and consider reallocating budget to higher-ROI channels.")
        if scores["customers"] < 50:
            suggestions.append("Invest in customer acquisition and retention programs.")
        if scores["cash_flow"] < 50:
            suggestions.append("Improve cash flow management — consider faster payment terms or inventory optimization.")
        if scores["operations"] < 50:
            suggestions.append("Enhance operational efficiency through automation or process improvement.")
        if not suggestions:
            suggestions.append("Business health is strong. Focus on sustained growth and market expansion.")

        return HealthScoreResponse(
            overall_score=round(overall, 1),
            category_scores={k: round(v, 1) for k, v in scores.items()},
            trend=trend,
            suggestions=suggestions,
        )
