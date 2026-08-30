"""Unit tests for Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from business_twin_ai.core.schemas.schemas import (
    AgentQuery,
    AgentResponse,
    BusinessData,
    ConfidenceResult,
    DecisionRequest,
    HealthScoreResponse,
    InsightResponse,
    Prediction,
    RecommendationResult,
    ScenarioResult,
    StrategyItem,
    WhatIfComparison,
    WhatIfRequest,
    WhatIfResponse,
    WhatIfScenario,
)


def test_business_data_defaults():
    """Test BusinessData with defaults."""
    data = BusinessData(name="Test")
    assert data.name == "Test"
    assert data.revenue == 0.0
    assert data.industry == "general"
    assert data.customers == 0


def test_business_data_custom():
    """Test BusinessData with custom values."""
    data = BusinessData(
        name="Custom Corp",
        industry="finance",
        revenue=500_000,
        expenses=300_000,
        customers=100,
    )
    assert data.revenue == 500_000
    assert data.customers == 100


def test_decision_request():
    """Test DecisionRequest validation."""
    req = DecisionRequest(
        decision_type="increase_price",
        decision_params={"percent": 10},
    )
    assert req.decision_type == "increase_price"
    assert req.decision_params["percent"] == 10


def test_decision_request_minimal():
    """Test DecisionRequest with empty params."""
    req = DecisionRequest(decision_type="open_branch")
    assert req.decision_params == {}


def test_scenario_result():
    """Test ScenarioResult."""
    s = ScenarioResult(
        label="Best Case",
        revenue=1_000_000,
        profit=300_000,
        roi=25.0,
        demand=120.0,
        risk=20.0,
        probability=30.0,
        explanation="Strong market conditions.",
    )
    assert s.label == "Best Case"
    assert s.revenue == 1_000_000


def test_confidence_result():
    """Test ConfidenceResult."""
    c = ConfidenceResult(
        score=85.0,
        level="High",
        reason="Good data quality.",
        supporting_factors=["Historical data available", "Market data present"],
    )
    assert c.score == 85.0
    assert c.level == "High"


def test_health_score_response():
    """Test HealthScoreResponse."""
    h = HealthScoreResponse(
        overall_score=75.0,
        category_scores={"finance": 80.0, "operations": 70.0},
        trend="improving",
        suggestions=["Optimize costs"],
    )
    assert h.overall_score == 75.0
    assert h.trend == "improving"
    assert len(h.suggestions) == 1


def test_what_if_request():
    """Test WhatIfRequest accepts 1–5 scenarios (single decisions are valid)."""
    with pytest.raises(ValidationError):
        WhatIfRequest(scenarios=[])

    single = WhatIfRequest(scenarios=[
        WhatIfScenario(name="A", decision_type="increase_price"),
    ])
    assert len(single.scenarios) == 1

    req = WhatIfRequest(scenarios=[
        WhatIfScenario(name="A", decision_type="increase_price"),
        WhatIfScenario(name="B", decision_type="increase_marketing"),
    ])
    assert len(req.scenarios) == 2


def test_agent_query():
    """Test AgentQuery validation."""
    q = AgentQuery(question="Should we increase prices?")
    assert q.question == "Should we increase prices?"

    with pytest.raises(ValidationError):
        AgentQuery(question="Hi")


def test_strategy_item():
    """Test StrategyItem."""
    s = StrategyItem(
        strategy_type="growth",
        title="Accelerate Growth",
        description="Focus on market expansion.",
        expected_impact={"revenue_increase": "20%"},
        reasoning="Strong fundamentals.",
        priority="high",
    )
    assert s.strategy_type == "growth"
    assert s.priority == "high"
