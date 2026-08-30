"""Specialized agents and the orchestrator that coordinates them.

Each agent follows a small loop: it plans what to inspect, calls the relevant
tools, records observations, and returns a synthesized finding. The orchestrator
runs the agents in dependency order, collects their findings, and produces a
final recommendation. Every step is recorded in `AgentStep` objects so the UI
can replay the full reasoning trace (the agentic-AI centerpiece).

When an LLM key is configured, the orchestrator asks the LLM to synthesize the
final answer from the collected observations; otherwise it uses deterministic
assembly so the demo still produces a coherent, fully-traced result.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.agentic.tools import build_tools
from business_twin_ai.core.schemas.schemas import AgentStep, NewsItem
from business_twin_ai.services.llm.client import get_llm_client
from business_twin_ai.services.prompts.templates import (
    SYNTHESIS_SYSTEM,
    SYNTHESIS_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class Agent:
    """Base agent: a named role with a tool set and a plan→observe→synthesize loop."""

    name = "agent"
    label = "Agent"
    description = ""
    tools: tuple = ()

    def __init__(self, db: AsyncSession, twin_id: uuid.UUID) -> None:
        self.db = db
        self.twin_id = twin_id
        self.tools = build_tools(db)
        self.steps: List[AgentStep] = []

    # ── step recording ─────────────────────────────────────────────────────

    def _record(self, phase: str, detail: str, agent: Optional[str] = None, tool: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> None:
        self.steps.append(
            AgentStep(agent=agent or self.name, phase=phase, tool=tool, detail=detail, data=data)
        )

    async def _tool_call(self, name: str, *args, **kwargs) -> Dict[str, Any]:
        start = time.monotonic()
        tool = self.tools[name]
        result = tool.executor(*args, **kwargs)
        if hasattr(result, "__await__"):
            result = await result
        duration = int((time.monotonic() - start) * 1000)
        self._record("tool_call", f"Calling tool `{name}`", tool=name, data={"args": [str(a)[:80] for a in args], "duration_ms": duration})
        self._record("observe", f"Tool `{name}` returned", tool=name, data=result)
        return result if isinstance(result, dict) else {"value": str(result)}

    async def run(self) -> Dict[str, Any]:
        raise NotImplementedError


class FinancialAgent(Agent):
    name = "financial"
    label = "Financial Analyst"
    description = "Analyzes revenue, profit, margins, cash flow and financial health."

    async def run(self) -> Dict[str, Any]:
        self._record("plan", "Inspecting the digital twin's financial state and health score.")
        state = await self._tool_call("twin_state", self.twin_id)
        health = await self._tool_call("health", self.twin_id)

        revenue = state.get("revenue", 0)
        profit = state.get("profit", 0)
        expenses = state.get("expenses", 0)
        margin = (profit / revenue * 100) if revenue else 0
        health_score = health.get("overall_score", 0)

        findings = {
            "revenue": revenue,
            "profit": profit,
            "expenses": expenses,
            "margin_pct": round(margin, 1),
            "health_score": health_score,
            "trend": health.get("trend", "stable"),
            "concerns": [],
            "strengths": [],
        }
        if margin < 10:
            findings["concerns"].append(f"Thin profit margin of {margin:.1f}% — cost pressure risk.")
        else:
            findings["strengths"].append(f"Healthy profit margin of {margin:.1f}%.")
        if expenses > revenue * 0.8:
            findings["concerns"].append("Expense ratio above 80% of revenue — little buffer for shocks.")
        if health_score < 50:
            findings["concerns"].append(f"Business health score is low ({health_score:.0f}/100).")
        self._record("synthesize", "Financial picture assembled.", data=findings)
        return findings


class MarketAgent(Agent):
    name = "market"
    label = "Market Intelligence"
    description = "Pulls live news and assesses market/geopolitical context."

    async def run(self, topics: Optional[List[str]] = None) -> Dict[str, Any]:
        state = {}
        try:
            state = await self._tool_call("twin_state", self.twin_id)
        except Exception:  # noqa: BLE001
            state = {}
        industry = state.get("industry", "business")
        topics = topics or [f"{industry}", "supply chain shipping", "global trade"]
        self._record("plan", f"Scanning live news for: {', '.join(topics)}.")

        all_news: List[Dict[str, Any]] = []
        for topic in topics[:3]:
            res = await self._tool_call("news", topic, 5)
            all_news.extend(res.get("articles", []))

        seen = set()
        unique: List[Dict[str, Any]] = []
        for a in all_news:
            t = a.get("title", "")
            if t and t not in seen:
                seen.add(t)
                unique.append(a)

        sentiment = self._assess_sentiment([n.get("title", "") for n in unique])
        self._record("synthesize", f"Market scan complete — {len(unique)} headlines, sentiment {sentiment}.", data={"count": len(unique), "sentiment": sentiment})
        return {"news": unique, "sentiment": sentiment, "headlines": [n.get("title", "") for n in unique[:5]]}

    def _assess_sentiment(self, titles: List[str]) -> str:
        neg = ["disrupt", "block", "war", "tension", "shortage", "crisis", "delay", "risk", "drought", "sanction", "tariff", "surge"]
        pos = ["growth", "recover", "record", "boost", "gain", "rise", "strong", "stabiliz", "expans"]
        score = 0
        for t in titles:
            t = t.lower()
            score += sum(1 for w in neg if w in t)
            score -= sum(1 for w in pos if w in t)
        if score >= 3:
            return "negative"
        if score >= 1:
            return "mixed"
        if score <= -2:
            return "positive"
        return "neutral"


class SupplyChainAgent(Agent):
    name = "supply_chain"
    label = "Supply Chain Analyst"
    description = "Assesses suppliers, inventory, shipments, risks and route exposure."

    async def run(self) -> Dict[str, Any]:
        self._record("plan", "Reviewing suppliers, inventory, shipments, active risks and today's route threats.")
        suppliers = await self._tool_call("suppliers")
        inventory = await self._tool_call("inventory")
        shipments = await self._tool_call("shipments")
        risks = await self._tool_call("risks")
        alerts = await self._tool_call("alerts")
        route_risk = await self._tool_call("route_risk")

        findings: Dict[str, Any] = {
            "suppliers": suppliers,
            "inventory": inventory,
            "shipments": shipments,
            "risks": risks,
            "alerts": alerts,
            "route_risk": route_risk,
            "concerns": [],
            "strengths": [],
        }
        high_risk = [s["name"] for s in suppliers.get("list", []) if s.get("risk_score", 0) > 60]
        if high_risk:
            findings["concerns"].append(f"High-risk suppliers: {', '.join(high_risk)}.")
        if inventory.get("low_stock"):
            findings["concerns"].append(f"Low-stock items: {', '.join(inventory['low_stock'][:3])}.")
        if shipments.get("delayed"):
            findings["concerns"].append(f"Delayed shipments: {', '.join(shipments['delayed'][:3])}.")
        critical = [r for r in risks.get("list", []) if r.get("severity") == "critical"]
        if critical:
            findings["concerns"].append(f"Critical risks: {', '.join(r['title'] for r in critical[:2])}.")
        # Today's chokepoint threats from the live risk radar (news-driven).
        top_risks = route_risk.get("top_risks", [])
        if top_risks:
            worst = top_risks[0]
            findings["route_exposure"] = worst
            findings["concerns"].append(
                f"Live chokepoint risk — {worst['chokepoint']} ({worst['event']}, "
                f"{worst['severity']}/{worst['risk_score']:.0f}). Headline: \"{worst['headline'][:70]}\""
            )
        if not findings["concerns"]:
            findings["strengths"].append("Supply chain shows no immediate red flags.")
        self._record("synthesize", "Supply chain assessment complete (incl. live route risk).", data=findings)
        return findings


class StrategyAgent(Agent):
    name = "strategy"
    label = "Strategy Advisor"
    description = "Turns findings into prioritized, actionable recommendations."

    async def run(self, financial: Dict[str, Any], market: Dict[str, Any], supply: Dict[str, Any]) -> Dict[str, Any]:
        self._record("plan", "Synthesizing findings into prioritized recommendations.")
        recommendations: List[str] = []
        rationale: List[str] = []

        # Financial-driven
        margin = financial.get("margin_pct", 0)
        if margin < 12:
            recommendations.append("Improve margins via pricing optimization or supplier cost renegotiation.")
            rationale.append(f"Profit margin is {margin:.1f}% — below the 12% resilience threshold.")
        if financial.get("health_score", 100) < 60:
            recommendations.append("Run a business-health turnaround simulation (cost reduction + revenue levers).")
            rationale.append(f"Health score is {financial.get('health_score'):.0f}/100.")

        # Market-driven
        sentiment = market.get("sentiment", "neutral")
        if sentiment == "negative":
            recommendations.append("Stress-test supply routes and pre-book alternative capacity.")
            rationale.append("Live market news sentiment is negative (disruptions/geopolitical risk).")
        elif sentiment == "positive":
            recommendations.append("Lean into growth: increase marketing and stock key products.")
            rationale.append("Live market news sentiment is positive.")

        # Supply-driven
        for c in supply.get("concerns", []):
            recommendations.append(c)
            rationale.append("Detected in live supply chain state.")

        # Route-risk driven — cite today's chokepoint threats explicitly.
        route_risk = supply.get("route_risk", {})
        top_risks = route_risk.get("top_risks", [])
        if top_risks:
            worst = top_risks[0]
            recommendations.append(
                f"Pre-book alternate capacity or reroute around {worst['chokepoint']} "
                f"({worst['event']}, risk {worst['risk_score']:.0f}/100) before it escalates."
            )
            rationale.append(f"Live risk radar flags {worst['chokepoint']} as the top chokepoint threat today.")
            for extra in top_risks[1:3]:
                if extra.get("severity") in ("critical", "high"):
                    recommendations.append(
                        f"Monitor {extra['chokepoint']} ({extra['event']}, risk {extra['risk_score']:.0f}/100) — elevated disruption odds."
                    )
                    rationale.append(f"Risk radar: {extra['chokepoint']} {extra['severity']} ({extra['risk_score']:.0f}/100).")

        if not recommendations:
            recommendations.append("Maintain current strategy and monitor KPIs — no urgent intervention flagged.")
            rationale.append("All agent findings are within healthy thresholds.")

        # De-duplicate while preserving order
        seen = set()
        recs = []
        for r in recommendations:
            if r not in seen:
                seen.add(r)
                recs.append(r)

        self._record("synthesize", f"{len(recs)} prioritized recommendations assembled.", data={"recommendations": recs})
        return {"recommendations": recs, "rationale": rationale, "priority": self._priority(recs)}

    def _priority(self, recs: List[str]) -> str:
        urgent = ["stress-test", "High-risk", "Critical", "low-stock", "immediate", "turnaround"]
        for r in recs:
            if any(u.lower() in r.lower() for u in urgent):
                return "high"
        return "medium"


class AgenticOrchestrator:
    """Runs the full multi-agent pipeline and produces a traced response."""

    def __init__(self, db: AsyncSession, twin_id: uuid.UUID) -> None:
        self.db = db
        self.twin_id = twin_id
        self.llm = get_llm_client()

    async def _ensure_twin(self) -> None:
        """Raise ValueError when the twin does not exist (→ 404 on the API)."""
        from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine

        engine = DigitalTwinEngine(self.db)
        if not await engine.get_twin(self.twin_id):
            raise ValueError(f"Digital twin {self.twin_id} not found")

    async def orchestrate(self, question: str = "Give me a complete business assessment") -> tuple:
        await self._ensure_twin()
        steps: List[AgentStep] = []
        start = time.monotonic()

        steps.append(AgentStep(agent="orchestrator", phase="plan", detail=f"Received request: {question[:120]}", data={"agents": ["financial", "market", "supply_chain", "strategy"]}))

        financial = FinancialAgent(self.db, self.twin_id)
        f_res = await financial.run()
        steps.extend(financial.steps)

        market = MarketAgent(self.db, self.twin_id)
        m_res = await market.run()
        steps.extend(market.steps)

        supply = SupplyChainAgent(self.db, self.twin_id)
        s_res = await supply.run()
        steps.extend(supply.steps)

        strategy = StrategyAgent(self.db, self.twin_id)
        st_res = await strategy.run(f_res, m_res, s_res)
        steps.extend(strategy.steps)

        steps.append(AgentStep(agent="orchestrator", phase="reflect", detail="Synthesizing final answer from all agent findings."))

        answer, mode = await self._synthesize_answer(question, f_res, m_res, s_res, st_res)
        duration = int((time.monotonic() - start) * 1000)
        steps.append(AgentStep(agent="orchestrator", phase="synthesize", detail=f"Completed in {duration}ms", data={"mode": mode}))

        news_items = [NewsItem(**{k: n[k] for k in ("title", "url", "source", "published_at", "language", "country") if k in n}) for n in m_res.get("news", [])]

        # Today's chokepoint threats (from the live risk radar) — surfaced to
        # the UI so users see exactly what the strategy agent is citing.
        chokepoint_risks = s_res.get("route_risk", {}).get("top_risks", [])

        return {
            "answer": answer,
            "recommendation": st_res["recommendations"][0] if st_res["recommendations"] else "Monitor and reassess.",
            "confidence": self._confidence(f_res, st_res),
            "mode": mode,
            "steps": steps,
            "news": news_items,
            "market_context": m_res.get("sentiment", "neutral"),
            "chokepoint_risks": chokepoint_risks,
        }, steps

    async def _synthesize_answer(self, question, f, m, s, st) -> tuple:
        """LLM synthesis when configured; deterministic assembly otherwise."""
        context = {
            "question": question,
            "financial": f,
            "market_headlines": m.get("headlines", []),
            "market_sentiment": m.get("sentiment", "neutral"),
            "supply_chain": s,
            "chokepoint_risks": s.get("route_risk", {}).get("top_risks", []),
            "recommendations": st["recommendations"],
        }
        try:
            answer = await self.llm.chat(SYNTHESIS_SYSTEM, format_prompt(SYNTHESIS_USER, context=str(context)))
            return answer, "llm"
        except Exception:  # noqa: BLE001
            return self._assembly_answer(f, m, s, st), "rule"

    def _assembly_answer(self, f, m, s, st) -> str:
        lines = ["## Agentic Assessment"]
        lines.append(f"- **Financial**: revenue ${f.get('revenue', 0):,.0f}, profit ${f.get('profit', 0):,.0f}, margin {f.get('margin_pct', 0):.1f}%, health {f.get('health_score', 0):.0f}/100.")
        h = m.get("headlines", [])
        if h:
            lines.append(f"- **Market**: sentiment {m.get('sentiment')} — top headline: \"{h[0]}\"")
        else:
            lines.append(f"- **Market**: sentiment {m.get('sentiment')} (no headlines captured)")
        sc = s.get("concerns", [])
        lines.append(f"- **Supply chain**: {len(sc)} concern(s)" + (f" — {'; '.join(sc[:2])}" if sc else " — no red flags."))
        top_risks = s.get("route_risk", {}).get("top_risks", [])
        if top_risks:
            worst = top_risks[0]
            lines.append(
                f"- **Route risk**: {worst['chokepoint']} is today's top chokepoint threat "
                f"({worst['event']}, risk {worst['risk_score']:.0f}/100)."
            )
        lines.append("")
        lines.append("**Recommended actions:**")
        for r in st.get("recommendations", []):
            lines.append(f"- {r}")
        return "\n".join(lines)

    def _confidence(self, f, st) -> float:
        base = 70.0
        if f.get("trend") == "improving":
            base += 5
        if st.get("priority") == "high":
            base += 5
        if f.get("health_score", 0) > 70:
            base += 5
        return round(min(95, base), 1)
