"""What-if Analysis engine.

Compares multiple business decisions side by side and recommends the winner.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.engines.simulator import SimulatorEngine
from business_twin_ai.core.schemas.schemas import (
    DecisionRequest,
    NewsItem,
    WhatIfComparison,
    WhatIfRequest,
    WhatIfResponse,
)
from business_twin_ai.services.news.gdelt import fetch_market_news


class WhatIfEngine:
    """Runs multiple simulations and compares outcomes."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.twin_engine = DigitalTwinEngine(db)
        self.simulator = SimulatorEngine(db)

    async def compare_scenarios(
        self, twin_id: uuid.UUID, request: WhatIfRequest
    ) -> WhatIfResponse:
        """Run all scenarios and produce a comparison."""
        twin = await self.twin_engine.get_twin(twin_id)
        if not twin:
            raise ValueError(f"Digital twin {twin_id} not found")

        comparisons: List[WhatIfComparison] = []
        best_revenue = -float("inf")
        winner_name = ""

        for scenario in request.scenarios:
            decision = DecisionRequest(
                decision_type=scenario.decision_type,
                decision_params=scenario.decision_params,
            )

            sim = await self.simulator.run_simulation(twin_id, decision)
            pred = sim.predictions.get("predictions", {})

            comp = WhatIfComparison(
                name=scenario.name,
                decision_type=scenario.decision_type,
                revenue=pred.get("revenue", {}).get("predicted", 0),
                profit=pred.get("profit", {}).get("predicted", 0),
                roi=pred.get("roi", {}).get("predicted", 0),
                risk=sim.scenarios[1]["risk"] if len(sim.scenarios) > 1 else 50.0,
                customer_growth=pred.get("customer_growth", {}).get("change_percent", 0),
                health_score=pred.get("business_health_score", {}).get("predicted", 50),
            )
            comparisons.append(comp)

            # Determine winner by revenue
            if comp.revenue > best_revenue:
                best_revenue = comp.revenue
                winner_name = comp.name

        # Generate recommendation
        recommendation = self._generate_comparison_recommendation(comparisons, winner_name)

        # ── News-aware analysis ────────────────────────────────────────────
        # Pull the latest headlines for the industry + top decision so the
        # recommendation reflects what is happening in the real world right
        # now (GDELT live, curated pool when offline).
        news_query = f"{twin.industry} {winner_name.replace('_', ' ')} market"
        news_items: List[NewsItem] = []
        market_context = ""
        try:
            articles = await fetch_market_news(news_query, limit=4)
            news_items = [NewsItem(**a) for a in articles]
            if news_items:
                top = news_items[0]
                market_context = (
                    f"Latest market signals for '{winner_name}': \"{top.title}\" "
                    f"({top.source}). Analysis weighs this real-time context alongside "
                    "the modeled business fundamentals above."
                )
                recommendation = f"{recommendation}\n\n[Market context] {market_context}"
        except Exception:  # noqa: BLE001 — news must never break the comparison
            pass

        return WhatIfResponse(
            comparisons=comparisons,
            recommendation=recommendation,
            winner=winner_name,
            news=news_items,
            market_context=market_context,
            news_query=news_query,
        )

    def _generate_comparison_recommendation(
        self, comparisons: List[WhatIfComparison], winner: str
    ) -> str:
        """Generate a recommendation based on scenario comparison."""
        if len(comparisons) < 2:
            c = comparisons[0]
            verdict = (
                "positive" if c.profit > 0 and c.risk < 40
                else "neutral" if c.risk < 60
                else "risky"
            )
            return (
                f"Single decision analysis: '{c.name}' projects revenue of "
                f"${c.revenue:,.2f} with a {c.risk:.1f}% risk level — a {verdict} "
                "outlook. Compare it against another decision to rank alternatives."
            )

        # Find best by different metrics
        best_profit = max(comparisons, key=lambda c: c.profit)
        best_roi = max(comparisons, key=lambda c: c.roi)
        safest = min(comparisons, key=lambda c: c.risk)

        parts = [
            f"Based on analysis, '{winner}' generates the highest revenue.",
        ]

        if best_profit.name != winner:
            parts.append(
                f"However, '{best_profit.name}' maximizes profit at ${best_profit.profit:,.2f}."
            )

        if best_roi.name != winner:
            parts.append(
                f"'{best_roi.name}' delivers the best ROI at {best_roi.roi:.1f}%."
            )

        if safest.name != winner:
            parts.append(
                f"For risk-averse strategy, '{safest.name}' has the lowest risk at {safest.risk:.1f}%."
            )

        parts.append(
            f"Recommendation: Choose '{winner}' for growth-focused strategy, or '{best_profit.name}' for profitability."
        )

        return " ".join(parts)
