"""Sample business dataset for demos and testing."""

from __future__ import annotations

from typing import Any, Dict

SAMPLE_BUSINESS_DATA: Dict[str, Any] = {
    "name": "TechNova Solutions",
    "industry": "technology",
    "description": "A mid-size SaaS company providing enterprise workflow automation tools.",
    "revenue": 5_200_000,
    "expenses": 3_800_000,
    "profit": 1_400_000,
    "cash_flow": 1_200_000,
    "customers": 850,
    "employees": 120,
    "products": {
        "WorkflowPro": {
            "type": "SaaS",
            "monthly_price": 299,
            "users": 600,
            "revenue": 2_160_000,
            "growth_rate": 0.12,
        },
        "AutomateFlow": {
            "type": "SaaS",
            "monthly_price": 499,
            "users": 200,
            "revenue": 1_200_000,
            "growth_rate": 0.08,
        },
        "DataSync": {
            "type": "Add-on",
            "monthly_price": 99,
            "users": 50,
            "revenue": 60_000,
            "growth_rate": 0.25,
        },
    },
    "sales": 4_800_000,
    "marketing_budget": 520_000,
    "pricing": {
        "WorkflowPro": 299,
        "AutomateFlow": 499,
        "DataSync": 99,
        "enterprise_tier": 999,
    },
    "inventory_summary": {
        "cloud_infrastructure_cost": 180_000,
        "license_costs": 45_000,
        "total_annual_cost": 225_000,
    },
    "warehouses": {
        "data_centers": 3,
        "regions": ["US-East", "EU-West", "APAC"],
        "redundancy": "high",
    },
    "competitors": {
        "FlowMaster": {"market_share": 18, "pricing": 349},
        "AutoBiz": {"market_share": 12, "pricing": 249},
        "WorkSync": {"market_share": 8, "pricing": 199},
    },
    "market_share": 8.5,
    "kpis": {
        "monthly_recurring_revenue": 433_333,
        "annual_recurring_revenue": 5_200_000,
        "customer_lifetime_value": 6_118,
        "customer_acquisition_cost": 612,
        "churn_rate": 3.2,
        "nps_score": 72,
        "net_revenue_retention": 115,
        "gross_margin": 78,
    },
    "raw_data": {
        "founded": 2019,
        "funding_stage": "Series B",
        "total_funding": 15_000_000,
        "target_market": "SMB & Mid-Market",
        "geographic_focus": ["North America", "Europe"],
    },
}

SAMPLE_SIMULATION_HISTORY = [
    {
        "decision_type": "increase_marketing",
        "decision_params": {"percent": 15, "channel": "digital"},
        "predicted_revenue": 5_980_000,
        "predicted_profit": 1_680_000,
        "confidence_score": 78.5,
    },
    {
        "decision_type": "launch_product",
        "decision_params": {"product_name": "AI Assist", "price": 199},
        "predicted_revenue": 6_240_000,
        "predicted_profit": 1_560_000,
        "confidence_score": 65.0,
    },
    {
        "decision_type": "hire_employees",
        "decision_params": {"count": 20, "department": "engineering"},
        "predicted_revenue": 5_720_000,
        "predicted_profit": 1_240_000,
        "confidence_score": 72.0,
    },
]


def get_sample_business() -> Dict[str, Any]:
    """Return the sample business data."""
    return SAMPLE_BUSINESS_DATA.copy()


def get_sample_simulations() -> list:
    """Return sample simulation history."""
    return SAMPLE_SIMULATION_HISTORY.copy()
