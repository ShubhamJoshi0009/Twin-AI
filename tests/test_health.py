"""Unit tests for the Business Health Score engine."""

from __future__ import annotations

import pytest

from business_twin_ai.core.engines.health import HealthEngine


def test_rule_based_health_healthy_business():
    """Test health scoring for a healthy business."""
    state = {
        "revenue": 5_000_000,
        "expenses": 3_000_000,
        "profit": 2_000_000,
        "cash_flow": 1_500_000,
        "customers": 500,
        "employees": 100,
        "sales": 4_500_000,
        "marketing_budget": 500_000,
        "market_share": 12.0,
        "products": {"P1": {}, "P2": {}, "P3": {}},
        "kpis": {},
    }

    engine = HealthEngine.__new__(HealthEngine)
    result = engine._rule_based_health(state)

    assert result.overall_score > 50
    assert result.trend == "improving"  # profit > 0 and cash_flow > 0
    assert len(result.suggestions) > 0
    assert "finance" in result.category_scores
    assert "marketing" in result.category_scores


def test_rule_based_health_struggling_business():
    """Test health scoring for a struggling business."""
    state = {
        "revenue": 100_000,
        "expenses": 150_000,
        "profit": -50_000,
        "cash_flow": -30_000,
        "customers": 20,
        "employees": 10,
        "sales": 80_000,
        "marketing_budget": 5_000,
        "market_share": 1.0,
        "products": {},
        "kpis": {},
    }

    engine = HealthEngine.__new__(HealthEngine)
    result = engine._rule_based_health(state)

    assert result.overall_score < 50
    assert result.trend == "declining"
    # Should have improvement suggestions
    assert any("cost" in s.lower() or "margin" in s.lower() or "profit" in s.lower() for s in result.suggestions)


def test_category_scores_range():
    """Test that all category scores are between 0 and 100."""
    state = {
        "revenue": 1_000_000,
        "expenses": 600_000,
        "profit": 400_000,
        "cash_flow": 300_000,
        "customers": 150,
        "employees": 30,
        "sales": 900_000,
        "marketing_budget": 100_000,
        "market_share": 6.0,
        "products": {"A": {}},
        "kpis": {},
    }

    engine = HealthEngine.__new__(HealthEngine)
    result = engine._rule_based_health(state)

    for category, score in result.category_scores.items():
        assert 0 <= score <= 100, f"{category} score {score} out of range"
