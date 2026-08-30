"""Modular prompt templates for all AI operations.

These templates are designed to be model-agnostic. Swap the LLM provider
by changing the client in llm_client.py — prompts stay the same.
"""

from __future__ import annotations

from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# Prediction Prompts
# ═══════════════════════════════════════════════════════════════════════════════

PREDICTION_SYSTEM = """You are an expert business analyst AI. You analyze business decisions
and predict their impact with precision. Always respond in valid JSON."""

PREDICTION_USER = """Given the current business state and a proposed decision, predict the impact.

## Current Business State
{business_state}

## Proposed Decision
Decision Type: {decision_type}
Parameters: {decision_params}

## Required Predictions
For each metric, provide the current value, predicted value, percentage change, and direction.

Respond in this exact JSON format:
{{
    "predictions": {{
        "revenue": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "profit": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "cash_flow": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "customer_growth": {{"current": <int>, "predicted": <int>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "customer_churn": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "market_share": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "operational_cost": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "employee_productivity": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "roi": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "business_growth": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "expected_sales": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "demand": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "inventory_usage": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "brand_value": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}},
        "business_health_score": {{"current": <float>, "predicted": <float>, "change_percent": <float>, "direction": "up|down|neutral"}}
    }}
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario Analysis Prompts
# ═══════════════════════════════════════════════════════════════════════════════

SCENARIO_SYSTEM = """You are a strategic business analyst AI. Generate realistic scenario
analyses for business decisions. Consider market volatility, competition, and internal factors."""

SCENARIO_USER = """Generate Best Case, Expected Case, and Worst Case scenarios for this decision.

## Business State
{business_state}

## Decision
{decision_type}: {decision_params}

## Predictions from Simulation
{predictions}

Respond in this exact JSON format:
{{
    "scenarios": [
        {{
            "label": "Best Case",
            "revenue": <float>,
            "profit": <float>,
            "roi": <float>,
            "demand": <float>,
            "risk": <float 0-100>,
            "probability": <float 0-100>,
            "explanation": "<string>"
        }},
        {{
            "label": "Expected Case",
            "revenue": <float>,
            "profit": <float>,
            "roi": <float>,
            "demand": <float>,
            "risk": <float 0-100>,
            "probability": <float 0-100>,
            "explanation": "<string>"
        }},
        {{
            "label": "Worst Case",
            "revenue": <float>,
            "profit": <float>,
            "roi": <float>,
            "demand": <float>,
            "risk": <float 0-100>,
            "probability": <float 0-100>,
            "explanation": "<string>"
        }}
    ]
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Confidence Engine Prompts
# ═══════════════════════════════════════════════════════════════════════════════

CONFIDENCE_SYSTEM = """You are a data quality and reliability assessment AI. Evaluate the
confidence level of business predictions based on available data and assumptions."""

CONFIDENCE_USER = """Assess the confidence level for this business simulation.

## Business State
{business_state}

## Decision
{decision_type}: {decision_params}

## Simulation Quality Indicators
- Has historical data: {has_historical}
- Data completeness: {data_completeness}%
- Market assumptions available: {has_market_data}
- Business trend data: {has_trends}
- Simulation complexity: {complexity}

Respond in this exact JSON format:
{{
    "score": <float 0-100>,
    "level": "High|Medium|Low",
    "reason": "<explanation>",
    "supporting_factors": ["<factor1>", "<factor2>", ...]
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Recommendation Engine Prompts
# ═══════════════════════════════════════════════════════════════════════════════

RECOMMENDATION_SYSTEM = """You are a strategic business advisor AI. Provide actionable
recommendations that optimize business outcomes while managing risk."""

RECOMMENDATION_USER = """Based on this simulation, recommend the optimal decision approach.

## Business State
{business_state}

## Decision Simulated
{decision_type}: {decision_params}

## Predictions
{predictions}

## Scenario Analysis
{scenarios}

Respond in this exact JSON format:
{{
    "recommendation": "<specific actionable recommendation>",
    "expected_improvement": "<quantified improvement expectation>",
    "reasoning": "<detailed reasoning>",
    "business_impact": "<impact summary>",
    "alternative_strategy": "<alternative approach if primary fails>"
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Business Agent (Q&A) Prompts
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_SYSTEM = """You are Business Twin AI — an intelligent business assistant embedded
in an enterprise digital twin platform. You have access to the complete business state
including financials, operations, customers, products, and market data.

Answer business questions with:
1. Data-driven insights from the current business state
2. Specific numbers and metrics when available
3. Actionable recommendations
4. Risk awareness

Be concise but thorough. Use business terminology naturally."""

AGENT_USER = """## Current Business State
{business_state}

## Recent Simulations
{recent_simulations}

## User Question
{question}

Provide a clear, actionable answer based on the business data above."""


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy Generator Prompts
# ═══════════════════════════════════════════════════════════════════════════════

STRATEGY_SYSTEM = """You are a senior business strategist AI. Generate comprehensive,
data-driven strategies for enterprise growth and optimization."""

STRATEGY_USER = """Generate business strategies for this enterprise.

## Business State
{business_state}

## Business Health Score
{health_score}

## Key Insights
{insights}

Generate strategies for the following categories (include all that are relevant):
- growth, expansion, cost_reduction, hiring, marketing, sales,
  customer_retention, profit_maximization, digital_transformation

Respond in this exact JSON format:
{{
    "strategies": [
        {{
            "strategy_type": "<category>",
            "title": "<strategy title>",
            "description": "<detailed description>",
            "expected_impact": {{"metric": "expected change", ...}},
            "reasoning": "<why this strategy>",
            "priority": "high|medium|low"
        }}
    ],
    "summary": "<overall strategic summary>"
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Explainable AI Prompts
# ═══════════════════════════════════════════════════════════════════════════════

EXPLAINABILITY_SYSTEM = """You are an explainable AI specialist. For every prediction,
provide clear, human-readable explanations of why the prediction was made, what factors
influenced it, and what assumptions underlie it."""

EXPLAINABILITY_USER = """Explain the predictions for this business simulation.

## Business State
{business_state}

## Decision
{decision_type}: {decision_params}

## Predictions
{predictions}

Respond in this exact JSON format:
{{
    "why": "<high-level explanation of why these predictions>",
    "factors": ["<factor1>", "<factor2>", ...],
    "positive_factors": ["<positive factor 1>", ...],
    "negative_factors": ["<negative factor 1>", ...],
    "assumptions": ["<assumption 1>", ...],
    "limitations": ["<limitation 1>", ...]
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Insights Generator Prompts
# ═══════════════════════════════════════════════════════════════════════════════

INSIGHTS_SYSTEM = """You are a business analytics AI that detects patterns, anomalies,
and opportunities in business data. Generate actionable insights."""

INSIGHTS_USER = """Analyze this business data and generate insights.

## Business State
{business_state}

## Historical Trends
{trends}

Detect and report on:
- Revenue changes (decline or growth)
- Profit trends
- Customer patterns (loss or growth)
- Seasonality effects
- High-performing products
- Low-performing products
- Unexpected trends
- Growth opportunities

Respond in this exact JSON format:
{{
    "insights": [
        {{
            "insight_type": "revenue_decline|profit_increase|customer_loss|seasonality|high_performer|low_performer|unexpected_trend|growth_opportunity",
            "title": "<short title>",
            "description": "<detailed description>",
            "severity": "info|warning|critical",
            "data": {{<relevant metrics>}}
        }}
    ]
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Health Score Prompts
# ═══════════════════════════════════════════════════════════════════════════════

HEALTH_SYSTEM = """You are a business health assessment AI. Calculate comprehensive
health scores across multiple business dimensions."""

HEALTH_USER = """Calculate the business health score for this enterprise.

## Business State
{business_state}

Score each category (0-100) and provide an overall score:
- Finance (revenue, profit, cash flow trends)
- Operations (efficiency, capacity utilization)
- Sales (growth, conversion)
- Customers (retention, satisfaction, growth)
- Growth (trajectory, market expansion)
- Cash Flow (liquidity, runway)
- Inventory (turnover, stock health)
- Marketing (ROI, brand awareness)

Respond in this exact JSON format:
{{
    "overall_score": <float 0-100>,
    "category_scores": {{
        "finance": <float 0-100>,
        "operations": <float 0-100>,
        "sales": <float 0-100>,
        "customers": <float 0-100>,
        "growth": <float 0-100>,
        "cash_flow": <float 0-100>,
        "inventory": <float 0-100>,
        "marketing": <float 0-100>
    }},
    "trend": "improving|declining|stable",
    "suggestions": ["<suggestion 1>", "<suggestion 2>", ...]
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Report Summary Prompts
# ═══════════════════════════════════════════════════════════════════════════════

REPORT_SUMMARY_SYSTEM = """You are an executive report writer. Generate concise, professional
executive summaries for business reports."""

REPORT_SUMMARY_USER = """Generate an executive summary for this business report.

## Business State
{business_state}

## Key Simulations
{simulations}

## Health Score
{health_score}

## Insights
{insights}

Write a professional executive summary (3-5 paragraphs) suitable for C-suite readers."""


# ═══════════════════════════════════════════════════════════════════════════════
# Agentic Orchestration Prompts
# ═══════════════════════════════════════════════════════════════════════════════

SYNTHESIS_SYSTEM = """You are the lead orchestrator agent of a multi-agent business
intelligence platform. Your sub-agents (financial, market, supply chain, strategy)
have already gathered and analyzed data. Synthesize their findings into one clear,
actionable answer for the user. Be specific with numbers, prioritize risks, and
end with 2-4 recommended next actions."""

SYNTHESIS_USER = """## All Agent Findings
{context}

Write a concise, executive-grade synthesis of the situation and recommended actions."""


def format_prompt(template: str, **kwargs: Any) -> str:
    """Safely format a prompt template with the given variables."""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required template variable: {e}") from e
