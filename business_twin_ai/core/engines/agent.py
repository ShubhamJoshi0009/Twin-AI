"""Business Decision Agent (LLM Q&A).

Answers natural language business questions using the current digital twin state.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.models.database import Simulation
from business_twin_ai.core.schemas.schemas import AgentResponse
from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.services.prompts.templates import AGENT_SYSTEM, AGENT_USER, format_prompt


class AgentEngine:
    """Natural language business assistant powered by LLM."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.twin_engine = DigitalTwinEngine(db)
        self.llm = get_llm_client()

    async def ask(self, twin_id: uuid.UUID, question: str) -> AgentResponse:
        """Answer a natural language question about the business."""
        twin = await self.twin_engine.get_twin(twin_id)
        if not twin:
            raise ValueError(f"Digital twin {twin_id} not found")

        state = self.twin_engine.get_twin_state(twin)

        # Fetch recent simulations for context
        recent_sims = await self._get_recent_simulations(twin_id)
        sims_context = self._format_simulations(recent_sims)

        # Build the prompt
        prompt = format_prompt(
            AGENT_USER,
            business_state=str(state),
            recent_simulations=sims_context,
            question=question,
        )

        try:
            response = await self.llm.chat(AGENT_SYSTEM, prompt)
            return AgentResponse(
                answer=response,
                context_used={
                    "twin_name": twin.name,
                    "revenue": twin.revenue,
                    "profit": twin.profit,
                    "customers": twin.customers,
                    "recent_simulations": len(recent_sims),
                },
                confidence=0.85,
            )
        except Exception:
            # Fallback: provide a structured rule-based answer
            return self._rule_based_answer(state, question, twin.name)

    async def _get_recent_simulations(self, twin_id: uuid.UUID, limit: int = 5) -> List[Simulation]:
        """Fetch recent simulations for context."""
        result = await self.db.execute(
            select(Simulation)
            .where(Simulation.twin_id == twin_id)
            .order_by(Simulation.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def _format_simulations(self, sims: List[Simulation]) -> str:
        """Format simulations for prompt context."""
        if not sims:
            return "No simulations run yet."

        lines = []
        for s in sims:
            lines.append(
                f"- {s.decision_type} on {s.created_at.strftime('%Y-%m-%d')}: "
                f"Revenue ${s.predicted_revenue:,.0f}, Profit ${s.predicted_profit:,.0f}, "
                f"Confidence {s.confidence_score:.0f}%"
            )
        return "\n".join(lines)

    def _rule_based_answer(
        self, state: Dict[str, Any], question: str, twin_name: str
    ) -> AgentResponse:
        """Provide a rule-based answer when LLM is unavailable."""
        question_lower = question.lower()
        revenue = state.get("revenue", 0)
        profit = state.get("profit", 0)
        customers = state.get("customers", 0)
        employees = state.get("employees", 0)
        expenses = state.get("expenses", 0)
        marketing = state.get("marketing_budget", 0)
        market_share = state.get("market_share", 0)

        if any(w in question_lower for w in ["price", "pricing"]):
            answer = (
                f"Regarding pricing at {twin_name}: Current revenue is ${revenue:,.0f} with "
                f"a profit of ${profit:,.0f}. "
                f"{'Consider reviewing pricing if margins are tight.' if profit < revenue * 0.1 else 'Current pricing appears sustainable.'} "
                f"To analyze the impact of price changes, run a simulation with increase_price or reduce_price decisions."
            )
        elif any(w in question_lower for w in ["store", "branch", "expand", "new location"]):
            answer = (
                f"Regarding expansion for {twin_name}: With ${revenue:,.0f} revenue and "
                f"{customers} customers, "
                f"{'expansion is viable with proper capital planning.' if profit > 0 else 'focus on profitability before expanding.'} "
                f"Run an 'open_branch' simulation to see projected outcomes."
            )
        elif any(w in question_lower for w in ["profit", "margin"]):
            margin = (profit / revenue * 100) if revenue > 0 else 0
            answer = (
                f"Profit analysis for {twin_name}: Revenue ${revenue:,.0f}, Profit ${profit:,.0f}, "
                f"Margin {margin:.1f}%. "
                f"{'Healthy margin.' if margin > 15 else 'Margin below target — consider cost optimization.' if margin > 0 else 'Currently unprofitable — urgent action needed.'}"
            )
        elif any(w in question_lower for w in ["revenue", "income", "sales"]):
            answer = (
                f"Revenue for {twin_name}: ${revenue:,.0f}. "
                f"Sales: ${state.get('sales', 0):,.0f}. "
                f"{'Revenue is trending positively.' if revenue > expenses else 'Revenue does not cover expenses — review strategy.'}"
            )
        elif any(w in question_lower for w in ["customer", "churn", "retention"]):
            answer = (
                f"Customer metrics for {twin_name}: {customers} customers, "
                f"Marketing budget: ${marketing:,.0f}. "
                f"{'Customer base is growing.' if customers > 100 else 'Consider investing in customer acquisition.'}"
            )
        elif any(w in question_lower for w in ["risk", "danger", "threat"]):
            answer = (
                f"Risk assessment for {twin_name}: "
                f"{'Primary risks include operating with negative cash flow.' if profit < 0 else 'Business appears stable.'} "
                f"Expenses at ${expenses:,.0f} {'are high relative to revenue.' if expenses > revenue * 0.8 else 'are within manageable range.'}"
            )
        elif any(w in question_lower for w in ["dashboard", "overview", "summary"]):
            answer = (
                f"Business Dashboard for {twin_name}:\n"
                f"• Revenue: ${revenue:,.0f}\n"
                f"• Expenses: ${expenses:,.0f}\n"
                f"• Profit: ${profit:,.0f}\n"
                f"• Customers: {customers}\n"
                f"• Employees: {employees}\n"
                f"• Market Share: {market_share:.1f}%\n"
                f"• Marketing Budget: ${marketing:,.0f}\n"
                f"{'Overall: Business is performing well.' if profit > 0 else 'Overall: Attention needed on profitability.'}"
            )
        elif any(w in question_lower for w in ["improve", "better", "optimize"]):
            answer = (
                f"Improvement areas for {twin_name}:\n"
                + ("• Optimize pricing for better margins\n" if profit < revenue * 0.15 else "")
                + ("• Increase marketing efficiency\n" if marketing < revenue * 0.1 else "")
                + ("• Focus on cost reduction\n" if expenses > revenue * 0.7 else "")
                + ("• Invest in customer retention\n" if customers < 500 else "")
                + "• Run simulations to test different strategies."
            )
        elif any(w in question_lower for w in ["strategy", "plan", "quarterly"]):
            answer = (
                f"Strategic recommendations for {twin_name}:\n"
                "1. Focus on core revenue drivers and optimize pricing\n"
                "2. Invest in customer acquisition and retention\n"
                "3. Monitor and optimize operational costs\n"
                "4. Build data-driven decision processes\n"
                "5. Use the Strategy Generator for detailed plans."
            )
        else:
            answer = (
                f"Regarding your question about {twin_name}: "
                f"Current business state shows ${revenue:,.0f} revenue, ${profit:,.0f} profit, "
                f"and {customers} customers. "
                f"Please ask specific questions about pricing, expansion, profit, customers, "
                f"risks, or run a simulation for detailed analysis."
            )

        return AgentResponse(
            answer=answer,
            context_used=state,
            confidence=0.6,
        )
