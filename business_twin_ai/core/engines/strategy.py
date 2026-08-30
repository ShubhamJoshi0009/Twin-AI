"""Strategy Generator engine.

Automatically generates business strategies across 9 categories:
growth, expansion, cost_reduction, hiring, marketing, sales,
customer_retention, profit_maximization, digital_transformation.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.engines.health import HealthEngine
from business_twin_ai.core.models.database import Strategy
from business_twin_ai.core.schemas.schemas import StrategyItem, StrategyResponse
from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.services.prompts.templates import (
    STRATEGY_SYSTEM,
    STRATEGY_USER,
    format_prompt,
)


class StrategyEngine:
    """Generates comprehensive business strategies."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.twin_engine = DigitalTwinEngine(db)
        self.health_engine = HealthEngine(db)
        self.llm = get_llm_client()

    async def generate_strategies(self, twin_id: uuid.UUID) -> StrategyResponse:
        """Generate strategies for the given digital twin."""
        twin = await self.twin_engine.get_twin(twin_id)
        if not twin:
            raise ValueError(f"Digital twin {twin_id} not found")

        state = self.twin_engine.get_twin_state(twin)

        # Get health score
        health = await self.health_engine.calculate_health(twin_id)
        health_json = str(health.model_dump())

        # Get insights
        insights = await self._get_quick_insights(state)
        insights_json = str(insights)

        # Try LLM strategy generation
        prompt = format_prompt(
            STRATEGY_USER,
            business_state=str(state),
            health_score=health_json,
            insights=insights_json,
        )

        try:
            data = await self.llm.chat_json(STRATEGY_SYSTEM, prompt)
            strategies = [StrategyItem(**s) for s in data.get("strategies", [])]
            summary = data.get("summary", "")
        except Exception:
            strategies = self._rule_based_strategies(state, health)
            summary = self._generate_summary(strategies, health)

        # Persist strategies
        for s in strategies:
            db_strategy = Strategy(
                twin_id=twin_id,
                strategy_type=s.strategy_type,
                title=s.title,
                description=s.description,
                expected_impact=s.expected_impact,
                reasoning=s.reasoning,
                priority=s.priority,
            )
            self.db.add(db_strategy)

        await self.db.flush()

        return StrategyResponse(strategies=strategies, summary=summary)

    async def _get_quick_insights(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get quick rule-based insights for strategy generation."""
        insights = []
        revenue = state.get("revenue", 0)
        profit = state.get("profit", 0)
        customers = state.get("customers", 0)
        expenses = state.get("expenses", 0)
        marketing = state.get("marketing_budget", 0)

        if profit < 0:
            insights.append({"type": "warning", "message": "Negative profit detected"})
        if expenses > revenue * 0.8:
            insights.append({"type": "warning", "message": "High expense ratio"})
        if marketing < revenue * 0.05:
            insights.append({"type": "opportunity", "message": "Marketing spend is low relative to revenue"})
        if customers < 100:
            insights.append({"type": "opportunity", "message": "Customer base is small — growth potential"})

        return insights

    def _rule_based_strategies(
        self, state: Dict[str, Any], health: Any
    ) -> List[StrategyItem]:
        """Generate rule-based strategies."""
        strategies: List[StrategyItem] = []
        revenue = state.get("revenue", 0)
        profit = state.get("profit", 0)
        expenses = state.get("expenses", 0)
        customers = state.get("customers", 0)
        employees = state.get("employees", 0)
        marketing = state.get("marketing_budget", 0)

        # Growth
        if revenue > 0:
            strategies.append(StrategyItem(
                strategy_type="growth",
                title="Accelerate Revenue Growth",
                description="Focus on expanding market reach and increasing sales velocity through targeted campaigns and product improvements.",
                expected_impact={"revenue_increase": "15-25%", "timeline": "6-12 months"},
                reasoning=f"Current revenue of ${revenue:,.0f} has room for growth with strategic investments.",
                priority="high",
            ))

        # Cost Reduction
        if expenses > revenue * 0.7:
            strategies.append(StrategyItem(
                strategy_type="cost_reduction",
                title="Optimize Operational Costs",
                description="Implement cost reduction measures targeting the top expense categories while maintaining quality.",
                expected_impact={"expense_reduction": "10-20%", "profit_improvement": "15-30%"},
                reasoning=f"Expense ratio of {expenses/revenue*100:.0f}% is above healthy threshold.",
                priority="high",
            ))

        # Marketing
        if marketing < revenue * 0.1:
            strategies.append(StrategyItem(
                strategy_type="marketing",
                title="Scale Marketing Investment",
                description="Increase marketing budget to capture market share and build brand awareness in target segments.",
                expected_impact={"customer_growth": "20-40%", "brand_awareness": "+25%"},
                reasoning="Marketing spend is below industry benchmarks relative to revenue.",
                priority="medium",
            ))

        # Customer Retention
        strategies.append(StrategyItem(
            strategy_type="customer_retention",
            title="Enhance Customer Retention Programs",
            description="Implement loyalty programs, improve customer service, and reduce churn through proactive engagement.",
            expected_impact={"churn_reduction": "15-25%", "ltv_increase": "20-30%"},
            reasoning="Retaining customers is 5-7x cheaper than acquiring new ones.",
            priority="medium",
        ))

        # Hiring
        if employees < 50:
            strategies.append(StrategyItem(
                strategy_type="hiring",
                title="Strategic Talent Acquisition",
                description="Hire key personnel in sales, engineering, and operations to support growth objectives.",
                expected_impact={"productivity_increase": "20-35%", "capacity_growth": "25%"},
                reasoning="Current team size may limit growth capacity.",
                priority="medium",
            ))

        # Profit Maximization
        if profit < revenue * 0.15:
            strategies.append(StrategyItem(
                strategy_type="profit_maximization",
                title="Improve Profit Margins",
                description="Focus on high-margin products, optimize pricing, and reduce waste to maximize profitability.",
                expected_impact={"margin_improvement": "5-10 percentage points"},
                reasoning="Current profit margins have significant room for improvement.",
                priority="high",
            ))

        # Digital Transformation
        strategies.append(StrategyItem(
            strategy_type="digital_transformation",
            title="Accelerate Digital Transformation",
            description="Invest in automation, data analytics, and digital tools to improve efficiency and decision-making.",
            expected_impact={"efficiency_gain": "15-30%", "cost_savings": "10-20%"},
            reasoning="Digital tools can significantly improve operational efficiency.",
            priority="low",
        ))

        # Expansion
        if revenue > 100000:
            strategies.append(StrategyItem(
                strategy_type="expansion",
                title="Geographic Market Expansion",
                description="Expand to new markets or regions to diversify revenue streams and capture new customer segments.",
                expected_impact={"revenue_increase": "20-40%", "market_coverage": "+30%"},
                reasoning="Strong revenue base supports expansion into adjacent markets.",
                priority="medium",
            ))

        # Sales
        strategies.append(StrategyItem(
            strategy_type="sales",
            title="Strengthen Sales Pipeline",
            description="Optimize sales processes, implement CRM improvements, and train sales team on consultative selling.",
            expected_impact={"conversion_rate": "+15-25%", "deal_size": "+10-20%"},
            reasoning="Sales efficiency improvements directly impact revenue.",
            priority="medium",
        ))

        return strategies

    def _generate_summary(self, strategies: List[StrategyItem], health: Any) -> str:
        """Generate a summary of all strategies."""
        high_priority = [s for s in strategies if s.priority == "high"]
        types = set(s.strategy_type for s in strategies)

        summary_parts = [
            f"Generated {len(strategies)} strategies across {len(types)} categories.",
        ]

        if high_priority:
            summary_parts.append(
                f"{len(high_priority)} high-priority strategies identified: "
                + ", ".join(s.title for s in high_priority) + "."
            )

        summary_parts.append(
            "Focus on high-impact, low-risk initiatives first for maximum ROI."
        )

        return " ".join(summary_parts)
