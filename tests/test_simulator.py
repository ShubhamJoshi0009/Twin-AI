"""Unit tests for the Simulator engine (rule-based fallbacks)."""

from __future__ import annotations

import pytest

from business_twin_ai.core.engines.simulator import SimulatorEngine, VALID_DECISIONS


def test_valid_decision_types():
    """Test that all expected decision types are defined."""
    expected = [
        "increase_price", "reduce_price", "open_branch", "close_branch",
        "hire_employees", "layoff_employees", "increase_marketing", "reduce_marketing",
        "launch_product", "stop_product", "enter_new_city", "change_supplier_cost",
        "increase_production_capacity",
    ]
    for dt in expected:
        assert dt in VALID_DECISIONS


def test_decision_descriptions():
    """Test that every decision type has a description."""
    for dt, config in VALID_DECISIONS.items():
        assert "description" in config, f"{dt} missing description"


def test_rule_based_predictions_increase_price():
    """Test rule-based predictions for increase_price."""
    state = {
        "revenue": 1_000_000,
        "expenses": 700_000,
        "profit": 300_000,
        "cash_flow": 250_000,
        "customers": 200,
        "employees": 50,
        "sales": 900_000,
        "marketing_budget": 100_000,
        "market_share": 5.0,
        "kpis": {"employee_productivity": 20_000},
    }

    # We need an instance but it requires a db session. Test the method directly.
    # Create a minimal mock to test the rule-based method.
    class MockEngine:
        def _rule_based_predictions(self, state, decision_type, params):
            return SimulatorEngine._rule_based_predictions(self, state, decision_type, params)

    engine = MockEngine()
    result = engine._rule_based_predictions(state, "increase_price", {"percent": 10})

    assert "predictions" in result
    preds = result["predictions"]
    assert "revenue" in preds
    assert "profit" in preds
    assert preds["revenue"]["direction"] == "up"
    assert preds["revenue"]["change_percent"] > 0


def test_rule_based_predictions_reduce_price():
    """Test rule-based predictions for reduce_price."""
    state = {
        "revenue": 1_000_000,
        "expenses": 700_000,
        "profit": 300_000,
        "cash_flow": 250_000,
        "customers": 200,
        "employees": 50,
        "sales": 900_000,
        "marketing_budget": 100_000,
        "market_share": 5.0,
        "kpis": {},
    }

    class MockEngine:
        def _rule_based_predictions(self, state, decision_type, params):
            return SimulatorEngine._rule_based_predictions(self, state, decision_type, params)

    engine = MockEngine()
    result = engine._rule_based_predictions(state, "reduce_price", {})

    preds = result["predictions"]
    assert preds["customer_growth"]["direction"] == "up"  # more customers with lower price
    assert preds["revenue"]["direction"] == "down"


def test_rule_based_scenarios():
    """Test rule-based scenario generation."""
    class MockEngine:
        def _rule_based_scenarios(self, state, request, predictions):
            return SimulatorEngine._rule_based_scenarios(self, state, request, predictions)

    engine = MockEngine()
    from business_twin_ai.core.schemas.schemas import DecisionRequest
    request = DecisionRequest(decision_type="hire_employees", decision_params={"count": 10})
    predictions = {
        "predictions": {
            "revenue": {"predicted": 1_100_000, "change_percent": 10},
            "profit": {"predicted": 270_000, "change_percent": -10},
        }
    }

    scenarios = engine._rule_based_scenarios({}, request, predictions)
    assert len(scenarios) == 3
    assert scenarios[0].label == "Best Case"
    assert scenarios[1].label == "Expected Case"
    assert scenarios[2].label == "Worst Case"
    assert scenarios[0].revenue > scenarios[1].revenue > scenarios[2].revenue


def test_rule_based_confidence():
    """Test rule-based confidence scoring."""
    class MockEngine:
        def _rule_based_confidence(self, completeness, has_historical, has_market):
            return SimulatorEngine._rule_based_confidence(self, completeness, has_historical, has_market)

    engine = MockEngine()
    result = engine._rule_based_confidence(90, True, True)
    assert result.score >= 75
    assert result.level == "High"
    assert len(result.supporting_factors) > 0

    result_low = engine._rule_based_confidence(20, False, False)
    assert result_low.score < 60
    assert result_low.level in ("Low", "Medium")
