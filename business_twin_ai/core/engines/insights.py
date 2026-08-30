"""Business Insights engine.

Automatically detects:
- Revenue decline
- Profit increase
- Customer loss
- Seasonality
- High-performing products
- Low-performing products
- Unexpected trends
- Growth opportunities
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.models.database import Insight
from business_twin_ai.core.schemas.schemas import InsightResponse
from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.services.news.gdelt import fetch_market_news
from business_twin_ai.services.prompts.templates import (
    INSIGHTS_SYSTEM,
    INSIGHTS_USER,
    format_prompt,
)


class InsightsEngine:
    """Generates and stores business insights."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.twin_engine = DigitalTwinEngine(db)
        self.llm = get_llm_client()

    async def generate_insights(self, twin_id: uuid.UUID) -> List[InsightResponse]:
        """Generate fresh insights for a digital twin."""
        twin = await self.twin_engine.get_twin(twin_id)
        if not twin:
            raise ValueError(f"Digital twin {twin_id} not found")

        state = self.twin_engine.get_twin_state(twin)

        # Try LLM insights
        prompt = format_prompt(
            INSIGHTS_USER,
            business_state=str(state),
            trends=str(state.get("kpis", {})),
        )

        try:
            data = await self.llm.chat_json(INSIGHTS_SYSTEM, prompt)
            raw_insights = data.get("insights", [])
        except Exception:
            raw_insights = self._rule_based_insights(state)

        # ── News-aware insight ─────────────────────────────────────────────
        # Surface the latest real-world headlines affecting the business so
        # the insight stream reflects current market conditions (GDELT live,
        # curated pool when offline). Best-effort — never blocks generation.
        try:
            news = await fetch_market_news(
                f"{state.get('industry', '')} {twin.name} supply chain market", limit=3
            )
            if news:
                headlines = " • ".join(n["title"] for n in news[:3])
                raw_insights.insert(0, {
                    "insight_type": "market_news",
                    "title": "Latest market news",
                    "description": f"Real-time headlines relevant to {twin.name}: {headlines}",
                    "severity": "info",
                    "data": {"headlines": [n["title"] for n in news[:3]], "sources": [n["source"] for n in news[:3]]},
                })
        except Exception:  # noqa: BLE001
            pass

        # Persist and return
        results: List[InsightResponse] = []
        for ins_data in raw_insights:
            insight = Insight(
                twin_id=twin_id,
                insight_type=ins_data.get("insight_type", "general"),
                title=ins_data.get("title", "Business Insight"),
                description=ins_data.get("description", ""),
                severity=ins_data.get("severity", "info"),
                data=ins_data.get("data"),
            )
            self.db.add(insight)
            await self.db.flush()

            results.append(InsightResponse(
                id=insight.id,
                insight_type=insight.insight_type,
                title=insight.title,
                description=insight.description,
                severity=insight.severity,
                data=insight.data,
                created_at=insight.created_at,
            ))

        return results

    async def get_insights(self, twin_id: uuid.UUID, limit: int = 20) -> List[InsightResponse]:
        """Fetch existing insights for a twin."""
        result = await self.db.execute(
            select(Insight)
            .where(Insight.twin_id == twin_id)
            .order_by(Insight.created_at.desc())
            .limit(limit)
        )
        insights = result.scalars().all()
        return [
            InsightResponse(
                id=i.id,
                insight_type=i.insight_type,
                title=i.title,
                description=i.description,
                severity=i.severity,
                data=i.data,
                created_at=i.created_at,
            )
            for i in insights
        ]

    def _rule_based_insights(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate insights using business rules."""
        insights: List[Dict[str, Any]] = []
        revenue = state.get("revenue", 0)
        profit = state.get("profit", 0)
        customers = state.get("customers", 0)
        expenses = state.get("expenses", 0)
        marketing = state.get("marketing_budget", 0)
        products = state.get("products", {})
        employees = state.get("employees", 0)

        # Revenue analysis
        if revenue > 0 and profit < 0:
            insights.append({
                "insight_type": "revenue_decline",
                "title": "Revenue Does Not Cover Costs",
                "description": f"Revenue of ${revenue:,.0f} is insufficient to cover ${expenses:,.0f} in expenses. Immediate cost optimization is recommended.",
                "severity": "critical",
                "data": {"revenue": revenue, "expenses": expenses, "deficit": expenses - revenue},
            })
        elif revenue > 0 and profit > 0:
            margin = profit / revenue * 100
            insights.append({
                "insight_type": "profit_increase",
                "title": "Healthy Profit Margins",
                "description": f"Business is generating a {margin:.1f}% profit margin on ${revenue:,.0f} revenue.",
                "severity": "info",
                "data": {"profit_margin": margin, "revenue": revenue, "profit": profit},
            })

        # Customer insights
        if customers > 0:
            rev_per_cust = revenue / customers
            insights.append({
                "insight_type": "growth_opportunity",
                "title": "Customer Revenue Analysis",
                "description": f"Average revenue per customer is ${rev_per_cust:,.2f}. With {customers} customers, there's potential to increase through upselling and retention.",
                "severity": "info",
                "data": {"revenue_per_customer": rev_per_cust, "total_customers": customers},
            })

        if customers < 100:
            insights.append({
                "insight_type": "customer_loss",
                "title": "Small Customer Base",
                "description": f"With only {customers} customers, the business should prioritize customer acquisition strategies.",
                "severity": "warning",
                "data": {"customers": customers},
            })

        # Marketing efficiency
        if marketing > 0:
            mktg_roi = revenue / marketing if marketing > 0 else 0
            if mktg_roi < 3:
                insights.append({
                    "insight_type": "low_performer",
                    "title": "Low Marketing ROI",
                    "description": f"Marketing ROI of {mktg_roi:.1f}x suggests inefficiency. Review channel performance and reallocate budget.",
                    "severity": "warning",
                    "data": {"marketing_roi": mktg_roi, "marketing_spend": marketing},
                })
            else:
                insights.append({
                    "insight_type": "high_performer",
                    "title": "Strong Marketing Performance",
                    "description": f"Marketing ROI of {mktg_roi:.1f}x indicates effective spend. Consider scaling successful channels.",
                    "severity": "info",
                    "data": {"marketing_roi": mktg_roi},
                })

        # Product insights
        if products:
            for name, details in products.items():
                if isinstance(details, dict):
                    prod_revenue = details.get("revenue", 0)
                    if prod_revenue > revenue * 0.3:
                        insights.append({
                            "insight_type": "high_performer",
                            "title": f"Star Product: {name}",
                            "description": f"Product '{name}' generates ${prod_revenue:,.0f} ({prod_revenue/revenue*100:.0f}% of total revenue). Consider doubling down on this product.",
                            "severity": "info",
                            "data": {"product": name, "revenue": prod_revenue},
                        })

        # Employee productivity
        if employees > 0:
            productivity = revenue / employees
            insights.append({
                "insight_type": "growth_opportunity",
                "title": "Employee Productivity",
                "description": f"Revenue per employee is ${productivity:,.0f}. {'Above industry average — team is efficient.' if productivity > 100000 else 'Consider process improvements to boost productivity.'}",
                "severity": "info",
                "data": {"revenue_per_employee": productivity, "employees": employees},
            })

        # Expense ratio
        if revenue > 0:
            expense_ratio = expenses / revenue * 100
            if expense_ratio > 80:
                insights.append({
                    "insight_type": "unexpected_trend",
                    "title": "High Expense Ratio",
                    "description": f"Expenses consume {expense_ratio:.0f}% of revenue. This is unsustainable — prioritize cost reduction.",
                    "severity": "critical",
                    "data": {"expense_ratio": expense_ratio},
                })

        # General growth opportunity
        if profit > 0 and customers < 1000:
            insights.append({
                "insight_type": "growth_opportunity",
                "title": "Scalability Opportunity",
                "description": f"With ${profit:,.0f} profit and {customers} customers, the business has capacity to scale operations.",
                "severity": "info",
                "data": {"profit": profit, "customers": customers},
            })

        return insights
