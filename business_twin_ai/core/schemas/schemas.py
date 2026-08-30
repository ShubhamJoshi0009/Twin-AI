"""Pydantic schemas for request/response validation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════════
# Digital Twin
# ═══════════════════════════════════════════════════════════════════════════════

class BusinessData(BaseModel):
    """Structured business data for creating / updating a digital twin."""

    name: str = Field(..., max_length=255, description="Business name")
    industry: str = Field(default="general", max_length=128)
    description: Optional[str] = None

    # Financials
    revenue: float = Field(default=0.0, ge=0)
    expenses: float = Field(default=0.0, ge=0)
    profit: float = Field(default=0.0)
    cash_flow: float = Field(default=0.0)

    # People
    customers: int = Field(default=0, ge=0)
    employees: int = Field(default=0, ge=0)

    # Products & Sales
    products: Optional[Dict[str, Any]] = None
    sales: float = Field(default=0.0, ge=0)
    marketing_budget: float = Field(default=0.0, ge=0)
    pricing: Optional[Dict[str, Any]] = None

    # Inventory & Logistics
    inventory_summary: Optional[Dict[str, Any]] = None
    warehouses: Optional[Dict[str, Any]] = None

    # Market
    competitors: Optional[Dict[str, Any]] = None
    market_share: float = Field(default=0.0, ge=0, le=100)

    # KPIs
    kpis: Optional[Dict[str, Any]] = None

    # Flexible extra data
    raw_data: Optional[Dict[str, Any]] = None


class DigitalTwinResponse(BaseModel):
    """Response schema for a digital twin."""

    id: uuid.UUID
    name: str
    industry: str
    description: Optional[str]
    revenue: float
    expenses: float
    profit: float
    cash_flow: float
    customers: int
    employees: int
    products: Optional[Dict[str, Any]]
    sales: float
    marketing_budget: float
    pricing: Optional[Dict[str, Any]]
    inventory_summary: Optional[Dict[str, Any]]
    warehouses: Optional[Dict[str, Any]]
    competitors: Optional[Dict[str, Any]]
    market_share: float
    kpis: Optional[Dict[str, Any]]
    business_health_score: float
    raw_data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceCheck(BaseModel):
    """A single field-level check inside a source checklist item."""

    field: str
    label: str
    present: bool
    value: str = ""


class SourceChecklistItem(BaseModel):
    """One audited data source that feeds a business profile (digital twin)."""

    source_id: str
    name: str
    category: str  # user-provided | financial | operational | market | ai-generated | real-time
    owner: str = ""  # which agent / input surface produces this section
    status: str  # verified | complete | partial | missing
    coverage_score: float = Field(ge=0, le=100)
    checks: List[SourceCheck] = Field(default_factory=list)
    last_updated: Optional[str] = None
    notes: str = ""
    # Saved state: user-marked completion, persisted via PUT /sources.
    completed: bool = False
    saved: bool = False  # True when completion was explicitly saved, not auto-derived


class SourceChecklistResponse(BaseModel):
    """The full data-source checklist for a business profile."""

    twin_id: uuid.UUID
    company: str
    industry: str
    overall_coverage: float = Field(ge=0, le=100)
    verified_count: int = 0
    complete_count: int = 0
    partial_count: int = 0
    missing_count: int = 0
    completed_count: int = 0
    total_sections: int = 0
    saved_at: Optional[str] = None
    items: List[SourceChecklistItem] = Field(default_factory=list)
    generated_at: datetime


class ChecklistSaveRequest(BaseModel):
    """Saved-state update: which profile sections are marked complete."""

    completions: Dict[str, bool] = Field(
        default_factory=dict,
        description="Map of source_id → completed flag to persist.",
    )


class ChecklistOverviewItem(BaseModel):
    """Coverage summary for one business profile (digital twin)."""

    twin_id: uuid.UUID
    company: str
    industry: str
    overall_coverage: float = Field(ge=0, le=100)
    completed_count: int = 0
    total_sections: int = 0
    verified_count: int = 0
    complete_count: int = 0
    partial_count: int = 0
    missing_count: int = 0
    regressed: bool = False
    last_audited_at: Optional[str] = None


class ChecklistOverviewResponse(BaseModel):
    """Per-profile coverage overview across all digital twins."""

    generated_at: datetime
    items: List[ChecklistOverviewItem] = Field(default_factory=list)


class ChecklistAuditSummary(BaseModel):
    """Result of a (scheduled or manual) source re-audit."""

    audited: int
    regressed: List[str] = Field(default_factory=list)
    ran_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Decision / Simulation
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionRequest(BaseModel):
    """A business decision to simulate."""

    decision_type: str = Field(
        ...,
        description=(
            "One of: increase_price, reduce_price, open_branch, close_branch, "
            "hire_employees, layoff_employees, increase_marketing, reduce_marketing, "
            "launch_product, stop_product, enter_new_city, change_supplier_cost, "
            "increase_production_capacity"
        ),
    )
    decision_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters specific to the decision type, e.g. percentage, city name, count.",
    )


class Prediction(BaseModel):
    """Single prediction metric."""

    metric: str
    current_value: float
    predicted_value: float
    change_percent: float
    direction: str  # "up" | "down" | "neutral"


class ScenarioResult(BaseModel):
    """One scenario (best / expected / worst)."""

    label: str  # "Best Case" | "Expected Case" | "Worst Case"
    revenue: float
    profit: float
    roi: float
    demand: float
    risk: float
    probability: float
    explanation: str


class ConfidenceResult(BaseModel):
    """AI confidence in the simulation."""

    score: float = Field(ge=0, le=100)
    level: str  # "High" | "Medium" | "Low"
    reason: str
    supporting_factors: List[str]


class RecommendationResult(BaseModel):
    """AI recommendation after simulation."""

    recommendation: str
    expected_improvement: str
    reasoning: str
    business_impact: str
    alternative_strategy: str


class ExplanationResult(BaseModel):
    """Explainable AI output for a prediction."""

    why: str
    factors: List[str]
    positive_factors: List[str]
    negative_factors: List[str]
    assumptions: List[str]
    limitations: List[str]


class SimulationResponse(BaseModel):
    """Full simulation response."""

    id: uuid.UUID
    twin_id: uuid.UUID
    decision_type: str
    decision_params: Dict[str, Any]
    predictions: Dict[str, Any]
    scenarios: List[ScenarioResult]
    confidence: ConfidenceResult
    recommendation: RecommendationResult
    explanation: ExplanationResult
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# What-If Comparison
# ═══════════════════════════════════════════════════════════════════════════════

class WhatIfScenario(BaseModel):
    """A single what-if scenario to compare."""

    name: str
    decision_type: str
    decision_params: Dict[str, Any] = Field(default_factory=dict)


class WhatIfRequest(BaseModel):
    """Request to compare multiple scenarios."""

    scenarios: List[WhatIfScenario] = Field(..., min_length=1, max_length=5)


class WhatIfComparison(BaseModel):
    """Comparison result for a single scenario."""

    name: str
    decision_type: str
    revenue: float
    profit: float
    roi: float
    risk: float
    customer_growth: float
    health_score: float


class NewsItem(BaseModel):
    """A single normalized news article."""

    title: str
    url: str
    source: str = ""
    published_at: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    sentiment: Optional[str] = None  # "positive" | "negative" | "neutral"


class WhatIfResponse(BaseModel):
    """Full what-if comparison response."""

    comparisons: List[WhatIfComparison]
    recommendation: str
    winner: str
    # Real-time market context backing the analysis (GDELT or curated fallback).
    news: List[NewsItem] = Field(default_factory=list)
    market_context: str = ""
    news_query: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Business Health
# ═══════════════════════════════════════════════════════════════════════════════

class HealthScoreResponse(BaseModel):
    """Business health score breakdown."""

    overall_score: float = Field(ge=0, le=100)
    category_scores: Dict[str, float]
    trend: str  # "improving" | "declining" | "stable"
    suggestions: List[str]


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy
# ═══════════════════════════════════════════════════════════════════════════════

class StrategyItem(BaseModel):
    """A single strategy recommendation."""

    strategy_type: str
    title: str
    description: str
    expected_impact: Dict[str, Any]
    reasoning: str
    priority: str  # "high" | "medium" | "low"


class StrategyResponse(BaseModel):
    """Strategy generation response."""

    strategies: List[StrategyItem]
    summary: str


# ═══════════════════════════════════════════════════════════════════════════════
# Business Agent (LLM Q&A)
# ═══════════════════════════════════════════════════════════════════════════════

class AgentQuery(BaseModel):
    """Natural language question about the business."""

    question: str = Field(..., min_length=3, max_length=2000)


class AgentResponse(BaseModel):
    """AI agent response."""

    answer: str
    context_used: Dict[str, Any]
    confidence: float


# ═══════════════════════════════════════════════════════════════════════════════
# Agentic AI (multi-agent orchestration, briefing, market watch)
# ═══════════════════════════════════════════════════════════════════════════════

class AgentStep(BaseModel):
    """One visible step in a multi-agent reasoning trace."""

    agent: str  # "orchestrator" | "financial" | "market" | "supply_chain" | "strategy"
    phase: str  # "plan" | "tool_call" | "observe" | "synthesize" | "reflect"
    tool: Optional[str] = None
    detail: str
    data: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None


class ChokepointRisk(BaseModel):
    """A single chokepoint risk surfaced by the live route risk radar."""

    chokepoint: str
    chokepoint_id: str = ""
    region: str = ""
    event: str = ""
    severity: str = ""
    risk_score: float = 0.0
    headline: str = ""


class OrchestrationResponse(BaseModel):
    """Full multi-agent orchestration result with a visible reasoning trace."""

    answer: str
    recommendation: str
    confidence: float
    mode: str  # "llm" | "rule"
    steps: List[AgentStep]
    news: List[NewsItem] = Field(default_factory=list)
    market_context: str = ""
    chokepoint_risks: List[ChokepointRisk] = Field(default_factory=list)


class BriefingSection(BaseModel):
    """A section of the executive briefing."""

    title: str
    body: str
    source: str  # which agent / tool produced it


class BriefingResponse(BaseModel):
    """One-shot executive briefing."""

    twin_id: uuid.UUID
    company: str
    industry: str
    generated_at: datetime
    summary: str
    health_score: float
    sections: List[BriefingSection]
    top_recommendations: List[str]
    news: List[NewsItem] = Field(default_factory=list)
    mode: str = "rule"  # "llm" | "rule"


class WatchItem(BaseModel):
    """A single market watch item (commodity / index / chokepoint)."""

    id: str
    name: str
    category: str  # "commodity" | "freight" | "geopolitical" | "index"
    trend: str  # "up" | "down" | "volatile" | "stable"
    sentiment: str  # "positive" | "negative" | "neutral" | "mixed"
    impact_score: float  # 0-100 — likely impact on the business
    direction: str  # "positive" | "negative" | "neutral" — effect on the business
    rationale: str
    news: List[NewsItem] = Field(default_factory=list)


class MarketWatchResponse(BaseModel):
    """Market watch dashboard data."""

    mode: str  # "live" | "curated"
    market_context: str
    items: List[WatchItem]
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Timeline
# ═══════════════════════════════════════════════════════════════════════════════

class TimelineEntry(BaseModel):
    """A single timeline entry."""

    simulation_id: uuid.UUID
    decision_type: str
    decision_params: Dict[str, Any]
    predicted_revenue: float
    predicted_profit: float
    confidence_score: float
    recommendation: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Insights
# ═══════════════════════════════════════════════════════════════════════════════

class InsightResponse(BaseModel):
    """A business insight."""

    id: uuid.UUID
    insight_type: str
    title: str
    description: str
    severity: str
    data: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════════

class ReportRequest(BaseModel):
    """Request to generate a PDF report."""

    include_simulations: bool = True
    include_insights: bool = True
    include_strategies: bool = True
    include_charts: bool = True


class ReportResponse(BaseModel):
    """Report generation response."""

    report_id: str
    download_url: str
    generated_at: datetime
    pages: int
