"""Executive briefing generator.

Runs the multi-agent pipeline once and compiles a structured, sectioned
briefing: summary, health, financials, market, supply chain, recommendations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.agentic.agents import AgenticOrchestrator
from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.schemas.schemas import BriefingResponse, BriefingSection


class BriefingGenerator:
    """Generates a one-shot executive briefing from the agentic pipeline."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.twin_engine = DigitalTwinEngine(db)

    async def generate(self, twin_id: uuid.UUID) -> BriefingResponse:
        twin = await self.twin_engine.get_twin(twin_id)
        if not twin:
            raise ValueError(f"Digital twin {twin_id} not found")

        orch = AgenticOrchestrator(self.db, twin_id)
        result, steps = await orch.orchestrate(question="Generate a full executive briefing")

        f = next((s.data for s in steps if s.agent == "financial" and s.phase == "synthesize"), {}) or {}
        m = next((s.data for s in steps if s.agent == "market" and s.phase == "synthesize"), {}) or {}
        sc = next((s.data for s in steps if s.agent == "supply_chain" and s.phase == "synthesize"), {}) or {}
        st = next((s.data for s in steps if s.agent == "strategy" and s.phase == "synthesize"), {}) or {}

        sections = [
            BriefingSection(
                title="Financial Position",
                body=(
                    f"Revenue ${f.get('revenue', 0):,.0f}, profit ${f.get('profit', 0):,.0f}, "
                    f"margin {f.get('margin_pct', 0):.1f}%, expenses ${f.get('expenses', 0):,.0f}. "
                    + (" ".join(f.get("concerns", [])) or "No financial red flags.")
                ),
                source="financial",
            ),
            BriefingSection(
                title="Market & News",
                body=(
                    f"Sentiment: {m.get('sentiment', 'neutral')}. "
                    + (" ".join(f"- {h}" for h in m.get("headlines", [])[:4]) or "No headlines captured.")
                ),
                source="market",
            ),
            BriefingSection(
                title="Supply Chain",
                body=(
                    f"{len(sc.get('concerns', []))} concern(s). "
                    + (" ".join(sc.get("concerns", [])) or "Supply chain operating within healthy thresholds.")
                ),
                source="supply_chain",
            ),
            BriefingSection(
                title="Recommended Actions",
                body="\n".join(f"- {r}" for r in st.get("recommendations", [])),
                source="strategy",
            ),
        ]

        return BriefingResponse(
            twin_id=twin_id,
            company=twin.name,
            industry=twin.industry,
            generated_at=datetime.now(timezone.utc),
            summary=result["answer"],
            health_score=f.get("health_score", 0),
            sections=sections,
            top_recommendations=st.get("recommendations", []),
            news=result.get("news", []),
            mode=result.get("mode", "rule"),
        )
