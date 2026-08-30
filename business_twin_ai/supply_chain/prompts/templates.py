"""Modular prompt templates for Supply Chain AI operations.

These templates are model-agnostic. Swap the LLM provider by changing
the client — prompts stay the same.
"""

from __future__ import annotations

from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# Supply Chain Agent (Q&A)
# ═══════════════════════════════════════════════════════════════════════════════

SC_AGENT_SYSTEM = """You are Supply Chain AI — an intelligent supply chain assistant embedded
in an enterprise digital twin platform. You have access to complete supply chain data
including suppliers, inventory, warehouses, shipments, and risk data.

Answer supply chain questions with:
1. Data-driven insights from current supply chain data
2. Specific numbers and metrics when available
3. Actionable recommendations
4. Risk awareness

Be concise but thorough. Use supply chain terminology naturally."""

SC_AGENT_USER = """## Current Supply Chain State
{supply_chain_state}

## Active Risks
{active_risks}

## Recent Alerts
{recent_alerts}

## User Question
{question}

Provide a clear, actionable answer based on the supply chain data above."""


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Prediction
# ═══════════════════════════════════════════════════════════════════════════════

SC_RISK_PREDICTION_SYSTEM = """You are a supply chain risk analyst AI. Predict future risks
based on historical data, current conditions, and market trends. Be precise and actionable."""

SC_RISK_PREDICTION_USER = """Predict supply chain risks for the next 30 days.

## Current Supply Chain State
{supply_chain_state}

## Historical Risk Data
{historical_risks}

## Active Risks
{active_risks}

Predict the following risks with probability and confidence:
- Supplier Failure Probability
- Delivery Delay Risk
- Inventory Shortage Risk
- Demand Spike Risk
- Demand Drop Risk
- Stockout Risk
- Warehouse Overflow Risk
- Transportation Delay Risk

Respond in this exact JSON format:
{{
    "predictions": [
        {{
            "risk_type": "<type>",
            "probability": <float 0-100>,
            "confidence": <float 0-100>,
            "timeframe": "<30 days|60 days|90 days>",
            "factors": ["<factor1>", "<factor2>"],
            "mitigation": "<recommended mitigation>"
        }}
    ],
    "overall_risk_level": "low|medium|high|critical"
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Supplier Recommendation
# ═══════════════════════════════════════════════════════════════════════════════

SC_SUPPLIER_RECOMMENDATION_SYSTEM = """You are a supply chain procurement AI. Recommend the best
suppliers based on cost, delivery performance, reliability, quality, and risk."""

SC_SUPPLIER_RECOMMENDATION_USER = """Recommend the best suppliers for this product category.

## Product Category
{product_category}

## Available Suppliers
{available_suppliers}

## Current Supply Chain State
{supply_chain_state}

Rank suppliers based on:
- Cost competitiveness
- Delivery performance (lead time, on-time rate)
- Reliability score
- Quality rating
- Capacity availability
- Risk score
- Location proximity

Respond in this exact JSON format:
{{
    "recommendations": [
        {{
            "supplier_id": "<uuid>",
            "supplier_name": "<name>",
            "score": <float 0-100>,
            "rank": <int>,
            "reasons": ["<reason1>", "<reason2>"],
            "cost_score": <float>,
            "delivery_score": <float>,
            "reliability_score": <float>,
            "quality_score": <float>
        }}
    ]
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Inventory Optimization
# ═══════════════════════════════════════════════════════════════════════════════

SC_INVENTORY_OPT_SYSTEM = """You are an inventory optimization AI. Analyze current inventory
levels and recommend optimal stock levels, reorder quantities, and transfers."""

SC_INVENTORY_OPT_USER = """Optimize inventory across all warehouses.

## Current Inventory
{current_inventory}

## Warehouse Status
{warehouse_status}

## Recent Demand Patterns
{demand_patterns}

Recommend:
- Reorder quantities for low-stock items
- Optimal safety stock levels
- Inter-warehouse transfers
- Overstock reduction actions
- Purchase planning

Respond in this exact JSON format:
{{
    "optimizations": [
        {{
            "product_name": "<name>",
            "product_sku": "<sku>",
            "warehouse_name": "<warehouse>",
            "current_stock": <int>,
            "recommended_reorder": <int>,
            "optimal_safety_stock": <int>,
            "transfer_quantity": <int or null>,
            "transfer_from": "<warehouse or null>",
            "transfer_to": "<warehouse or null>",
            "urgency": "immediate|soon|normal",
            "estimated_cost_saving": <float>
        }}
    ],
    "optimization_score": <float 0-100>,
    "total_potential_saving": <float>
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Route Optimization
# ═══════════════════════════════════════════════════════════════════════════════

SC_ROUTE_OPT_SYSTEM = """You are a logistics optimization AI. Generate optimal delivery
routes that minimize time, fuel cost, and transportation expenses."""

SC_ROUTE_OPT_USER = """Optimize delivery routes for these shipments.

## Active Shipments
{active_shipments}

## Warehouse Locations
{warehouse_locations}

## Route Constraints
{route_constraints}

Optimize routes to minimize:
- Travel time
- Fuel cost
- Transportation cost
- Delivery delays

Respond in this exact JSON format:
{{
    "routes": [
        {{
            "origin": "<location>",
            "destination": "<location>",
            "optimized_route": "<route description>",
            "estimated_time_hours": <float>,
            "distance_km": <float>,
            "fuel_saved": <float>,
            "cost_saved": <float>,
            "efficiency_improvement": <float>
        }}
    ],
    "total_fuel_saved": <float>,
    "total_cost_saved": <float>
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario Analysis
# ═══════════════════════════════════════════════════════════════════════════════

SC_SCENARIO_SYSTEM = """You are a supply chain simulation AI. Analyze the impact of
disruptive events on the supply chain and provide actionable recommendations."""

SC_SCENARIO_USER = """Simulate the impact of this supply chain scenario.

## Scenario
Type: {scenario_type}
Parameters: {scenario_parameters}

## Current Supply Chain State
{supply_chain_state}

Predict the impact on:
- Inventory levels
- Delivery schedules
- Revenue
- Operations
- Lead times
- Risk score

Respond in this exact JSON format:
{{
    "impact": {{
        "inventory_impact": "<description>",
        "delivery_impact": "<description>",
        "revenue_impact": "<description>",
        "operations_impact": "<description>",
        "lead_time_impact": "<description>",
        "risk_score_change": <float>,
        "severity": "low|medium|high|critical"
    }},
    "recommendations": ["<recommendation1>", "<recommendation2>"]
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Optimization Engine
# ═══════════════════════════════════════════════════════════════════════════════

SC_OPTIMIZATION_SYSTEM = """You are a supply chain optimization AI. Analyze the entire
supply chain and recommend actions to reduce costs and improve efficiency."""

SC_OPTIMIZATION_USER = """Analyze and optimize the supply chain.

## Current Supply Chain State
{supply_chain_state}

## Cost Analysis
{cost_analysis}

## Performance Metrics
{performance_metrics}

Recommend actions to:
- Reduce logistics costs
- Reduce supplier risks
- Improve warehouse utilization
- Reduce inventory holding costs
- Improve delivery performance
- Balance warehouse load
- Optimize procurement
- Increase supply chain efficiency

Respond in this exact JSON format:
{{
    "recommendations": [
        {{
            "category": "logistics|supplier|warehouse|inventory|procurement",
            "title": "<recommendation title>",
            "description": "<detailed description>",
            "expected_saving": <float>,
            "priority": "high|medium|low",
            "implementation_effort": "low|medium|high"
        }}
    ],
    "total_potential_saving": <float>,
    "efficiency_improvement": <float>
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Supply Chain Health Score
# ═══════════════════════════════════════════════════════════════════════════════

SC_HEALTH_SYSTEM = """You are a supply chain health assessment AI. Calculate comprehensive
health scores across multiple supply chain dimensions."""

SC_HEALTH_USER = """Calculate the supply chain health score.

## Supply Chain State
{supply_chain_state}

Score each category (0-100):
- Supplier Performance
- Inventory Health
- Warehouse Efficiency
- Transportation
- Delivery Performance
- Demand Fulfillment
- Risk Level
- Cost Efficiency

Respond in this exact JSON format:
{{
    "overall_score": <float 0-100>,
    "category_scores": {{
        "supplier_performance": <float>,
        "inventory_health": <float>,
        "warehouse_efficiency": <float>,
        "transportation": <float>,
        "delivery_performance": <float>,
        "demand_fulfillment": <float>,
        "risk_level": <float>,
        "cost_efficiency": <float>
    }},
    "trend": "improving|declining|stable",
    "suggestions": ["<suggestion1>", "<suggestion2>"]
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Explainable AI
# ═══════════════════════════════════════════════════════════════════════════════

SC_EXPLAINABILITY_SYSTEM = """You are a supply chain explainable AI specialist. For every
recommendation, provide clear explanations of why it was made, what factors influenced it,
and what the expected outcomes are."""

SC_EXPLAINABILITY_USER = """Explain this supply chain recommendation.

## Recommendation
{recommendation}

## Supply Chain Context
{context}

Respond in this exact JSON format:
{{
    "why": "<explanation of why this recommendation>",
    "factors": ["<factor1>", "<factor2>"],
    "expected_benefits": ["<benefit1>", "<benefit2>"],
    "possible_risks": ["<risk1>", "<risk2>"],
    "assumptions": ["<assumption1>", "<assumption2>"],
    "confidence": <float 0-100>
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# Report Summary
# ═══════════════════════════════════════════════════════════════════════════════

SC_REPORT_SUMMARY_SYSTEM = """You are an executive report writer for supply chain operations.
Generate concise, professional executive summaries for supply chain reports."""

SC_REPORT_SUMMARY_USER = """Generate an executive summary for this supply chain report.

## Supply Chain Overview
{supply_chain_overview}

## Key Metrics
{key_metrics}

## Health Score
{health_score}

## Recent Risks
{recent_risks}

Write a professional executive summary (3-5 paragraphs) suitable for operations leaders."""


def format_prompt(template: str, **kwargs: Any) -> str:
    """Safely format a prompt template with the given variables."""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required template variable: {e}") from e
