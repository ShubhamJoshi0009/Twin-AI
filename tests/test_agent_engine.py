"""Unit tests for the Business Decision Agent's rule-based fallback.

The LLM path is exercised through the API integration tests; these tests lock
in the deterministic ``_rule_based_answer`` branches so every question category
(pricing, expansion, profit, revenue, customers, risk, dashboard, improve,
strategy, generic) is covered without a network or API key.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from business_twin_ai.core.engines.agent import AgentEngine
from business_twin_ai.core.models.database import Simulation
from business_twin_ai.database import Base
from business_twin_ai.core.schemas.schemas import BusinessData
from business_twin_ai.supply_chain.engines.agent import SupplyChainAgentEngine

# A healthy-ish trading state reused across branches.
STATE = {
    "name": "Acme Corp",
    "revenue": 1_000_000,
    "expenses": 600_000,
    "profit": 400_000,
    "cash_flow": 250_000,
    "customers": 500,
    "employees": 80,
    "sales": 950_000,
    "marketing_budget": 100_000,
    "market_share": 8.0,
    "kpis": {"profit_margin": 40.0},
}


def _engine() -> AgentEngine:
    # No DB session needed for the pure rule-based method.
    return AgentEngine.__new__(AgentEngine)


def test_rule_based_pricing_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "Should we review pricing?", "Acme Corp")
    assert resp.confidence == 0.6
    assert "pricing" in resp.answer.lower()
    assert resp.context_used == STATE


def test_rule_based_pricing_tight_margin() -> None:
    """When profit < 10% of revenue, pricing advice recommends a review."""
    tight = {**STATE, "revenue": 1_000_000, "profit": 50_000}
    resp = _engine()._rule_based_answer(tight, "how about prices", "Acme Corp")
    assert "Consider reviewing pricing if margins are tight" in resp.answer


def test_rule_based_expansion_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "Should we open a new store in Chicago?", "Acme Corp")
    assert "expansion" in resp.answer.lower()
    assert "open_branch" in resp.answer


def test_rule_based_expansion_unprofitable() -> None:
    """Unprofitable businesses are advised to fix margins before expanding."""
    loss = {**STATE, "profit": -50_000}
    resp = _engine()._rule_based_answer(loss, "expand to a new location?", "Acme Corp")
    assert "focus on profitability before expanding" in resp.answer


def test_rule_based_profit_question() -> None:
    """Profit/margin branch — the one uncovered by the trimmed integration file."""
    resp = _engine()._rule_based_answer(STATE, "How is our profit and margin?", "Acme Corp")
    assert "Profit analysis" in resp.answer
    assert "Margin 40.0%" in resp.answer
    assert "Healthy margin" in resp.answer


def test_rule_based_profit_low_margin() -> None:
    resp = _engine()._rule_based_answer({**STATE, "profit": 100_000}, "what about margins", "Acme Corp")
    assert "Margin below target" in resp.answer


def test_rule_based_profit_unprofitable() -> None:
    resp = _engine()._rule_based_answer({**STATE, "profit": -10_000}, "profit?", "Acme Corp")
    assert "Currently unprofitable" in resp.answer


def test_rule_based_profit_zero_revenue() -> None:
    """Zero revenue must not raise a division-by-zero error."""
    resp = _engine()._rule_based_answer({**STATE, "revenue": 0, "profit": 0}, "profit margin", "Acme Corp")
    assert "Margin 0.0%" in resp.answer


def test_rule_based_revenue_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "What is our revenue this year?", "Acme Corp")
    assert "Revenue for Acme Corp" in resp.answer
    assert "trending positively" in resp.answer


def test_rule_based_revenue_not_covering_expenses() -> None:
    resp = _engine()._rule_based_answer(
        {**STATE, "revenue": 100_000, "expenses": 200_000}, "sales?", "Acme Corp"
    )
    assert "Revenue does not cover expenses" in resp.answer


def test_rule_based_customer_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "How many customers do we have?", "Acme Corp")
    assert "Customer metrics" in resp.answer
    assert "Customer base is growing" in resp.answer


def test_rule_based_customer_acquisition() -> None:
    resp = _engine()._rule_based_answer({**STATE, "customers": 50}, "customer churn", "Acme Corp")
    assert "Consider investing in customer acquisition" in resp.answer


def test_rule_based_risk_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "What are our main risks?", "Acme Corp")
    assert "Risk assessment" in resp.answer
    assert "Business appears stable" in resp.answer


def test_rule_based_risk_negative_cashflow() -> None:
    resp = _engine()._rule_based_answer(
        {**STATE, "profit": -20_000, "expenses": 900_000}, "is there any threat?", "Acme Corp"
    )
    assert "Primary risks include operating with negative cash flow" in resp.answer
    assert "are high relative to revenue" in resp.answer


def test_rule_based_dashboard_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "show me the dashboard overview", "Acme Corp")
    assert "Business Dashboard" in resp.answer
    assert "Revenue: $1,000,000" in resp.answer
    assert "Market Share: 8.0%" in resp.answer
    assert "Business is performing well" in resp.answer


def test_rule_based_dashboard_attention_needed() -> None:
    resp = _engine()._rule_based_answer({**STATE, "profit": -5_000}, "summary please", "Acme Corp")
    assert "Attention needed on profitability" in resp.answer


def test_rule_based_improve_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "how can we improve?", "Acme Corp")
    assert "Improvement areas" in resp.answer
    assert "Run simulations" in resp.answer


def test_rule_based_improve_all_areas() -> None:
    """When every lever is underperforming, all improvement bullets appear."""
    weak = {
        **STATE,
        "revenue": 1_000_000,
        "profit": 100_000,  # < 15% → pricing
        "marketing_budget": 50_000,  # < 10% → marketing
        "expenses": 900_000,  # > 70% → costs
        "customers": 200,  # < 500 → retention
    }
    resp = _engine()._rule_based_answer(weak, "optimize the business better", "Acme Corp")
    for bullet in [
        "Optimize pricing",
        "Increase marketing efficiency",
        "Focus on cost reduction",
        "Invest in customer retention",
    ]:
        assert bullet in resp.answer


def test_rule_based_strategy_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "what is our quarterly strategy plan?", "Acme Corp")
    assert "Strategic recommendations" in resp.answer
    assert "Strategy Generator" in resp.answer


def test_rule_based_generic_question() -> None:
    resp = _engine()._rule_based_answer(STATE, "tell me something about the weather", "Acme Corp")
    assert "Regarding your question about Acme Corp" in resp.answer
    assert "Please ask specific questions" in resp.answer


def test_format_simulations_empty() -> None:
    assert _engine()._format_simulations([]) == "No simulations run yet."


def test_format_simulations_nonempty() -> None:
    sims = [
        Simulation(
            id=uuid.uuid4(),
            twin_id=uuid.uuid4(),
            decision_type="increase_price",
            decision_params={},
            predicted_revenue=1_100_000,
            predicted_profit=450_000,
            confidence_score=82.5,
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
    ]
    out = _engine()._format_simulations(sims)
    assert "increase_price on 2026-07-01" in out
    assert "Revenue $1,100,000" in out
    assert "Confidence 82%" in out


# ═══════════════════════════════════════════════════════════════════════════
# AgentEngine.ask() — twin-not-found error path (line 33) + LLM-success path
# (line 51), which the API-only tests never hit directly.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_ask_unknown_twin_raises(db_session: AsyncSession) -> None:
    """Asking about a non-existent twin raises ValueError (not a 200 with junk)."""
    engine = AgentEngine(db_session)
    with pytest.raises(ValueError, match="not found"):
        await engine.ask(uuid.uuid4(), "How is profit?")


@pytest.mark.asyncio
async def test_ask_llm_success_path(db_session: AsyncSession) -> None:
    """When the LLM client succeeds, the response carries LLM text + confidence."""
    from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine

    twin = await DigitalTwinEngine(db_session).create_twin(
        BusinessData(name="Acme Corp", industry="technology", revenue=1_000_000, expenses=600_000)
    )
    engine = AgentEngine(db_session)

    class _FakeLLM:
        async def chat(self, system, prompt):
            return "LLM says: pricing looks sustainable."

    engine.llm = _FakeLLM()
    resp = await engine.ask(twin.id, "Should we review pricing?")
    assert resp.answer == "LLM says: pricing looks sustainable."
    assert resp.confidence == 0.85
    assert resp.context_used["recent_simulations"] == 0


@pytest.mark.asyncio
async def test_ask_llm_failure_falls_back_to_rules(db_session: AsyncSession) -> None:
    """When the LLM raises, the rule-based fallback is used (confidence 0.6)."""
    from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine

    twin = await DigitalTwinEngine(db_session).create_twin(
        BusinessData(name="Acme Corp", industry="technology", revenue=1_000_000, expenses=600_000)
    )
    engine = AgentEngine(db_session)

    class _BoomLLM:
        async def chat(self, system, prompt):
            raise RuntimeError("no key")

    engine.llm = _BoomLLM()
    resp = await engine.ask(twin.id, "How is profit and margin?")
    assert resp.confidence == 0.6
    assert "Profit analysis" in resp.answer


# ═══════════════════════════════════════════════════════════════════════════
# SupplyChainAgentEngine._rule_based_answer — branches the API tests miss
# (warehouse, shipment, risk, cost, reorder, alert, generic).
# ═══════════════════════════════════════════════════════════════════════════

SC_STATE = {
    "total_suppliers": 4,
    "avg_reliability": 78.5,
    "high_risk_suppliers": 1,
    "total_warehouses": 3,
    "avg_utilization": 64.0,
    "overloaded_warehouses": 1,
    "total_inventory": 12_000,
    "low_stock_items": 2,
    "overstock_items": 1,
    "total_shipments": 10,
    "in_transit": 4,
    "delayed_shipments": 1,
    "total_transport_cost": 12_500.0,
    "total_fuel_cost": 3_200.0,
}


SC_RISKS = [{"type": "supplier_failure", "score": 80, "severity": "critical"}]
SC_ALERTS = [{"title": "Stock low", "severity": "high"}]


def _sc_engine() -> SupplyChainAgentEngine:
    return SupplyChainAgentEngine.__new__(SupplyChainAgentEngine)


def test_sc_rule_based_supplier() -> None:
    resp = _sc_engine()._rule_based_answer("which supplier is risky?", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "4 active suppliers" in resp.answer
    assert "1 suppliers are high-risk" in resp.answer
    assert resp.confidence == 0.6


def test_sc_rule_based_inventory() -> None:
    resp = _sc_engine()._rule_based_answer("inventory levels?", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "Total inventory: 12000 units" in resp.answer
    assert "2 items are below reorder level" in resp.answer


def test_sc_rule_based_warehouse() -> None:
    resp = _sc_engine()._rule_based_answer("warehouse storage capacity", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "3 warehouses operational" in resp.answer
    assert "Average utilization: 64.0%" in resp.answer
    assert "1 warehouses are above 90% capacity" in resp.answer


def test_sc_rule_based_shipment() -> None:
    resp = _sc_engine()._rule_based_answer("shipment delivery status", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "10 total shipments" in resp.answer
    assert "4 in transit, 1 delayed" in resp.answer
    assert "$12,500.00" in resp.answer


def test_sc_rule_based_risk() -> None:
    resp = _sc_engine()._rule_based_answer("any supply chain threats?", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "1 active risks detected" in resp.answer
    assert "Top risks: supplier_failure" in resp.answer


def test_sc_rule_based_risk_empty() -> None:
    resp = _sc_engine()._rule_based_answer("danger analysis", SC_STATE, [], SC_ALERTS)
    assert "Top risks: None" in resp.answer


def test_sc_rule_based_cost() -> None:
    resp = _sc_engine()._rule_based_answer("how can we cut costs?", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "Total transport cost: $12,500.00" in resp.answer
    assert "Total fuel cost: $3,200.00" in resp.answer
    assert "save ~15%" in resp.answer


def test_sc_rule_based_reorder() -> None:
    resp = _sc_engine()._rule_based_answer("what needs reordering?", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "2 items need reordering" in resp.answer


def test_sc_rule_based_alert() -> None:
    resp = _sc_engine()._rule_based_answer("show me alerts", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "1 active alerts" in resp.answer
    assert "Latest: Stock low" in resp.answer


def test_sc_rule_based_alert_empty() -> None:
    resp = _sc_engine()._rule_based_answer("any notifications?", SC_STATE, SC_RISKS, [])
    assert "0 active alerts" in resp.answer
    assert "No active alerts." in resp.answer


def test_sc_rule_based_generic() -> None:
    resp = _sc_engine()._rule_based_answer("give me an overview", SC_STATE, SC_RISKS, SC_ALERTS)
    assert "Supply Chain Overview" in resp.answer
    assert "4 suppliers, 3 warehouses, 12000 inventory units" in resp.answer
