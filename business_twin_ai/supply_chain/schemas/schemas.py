"""Pydantic schemas for the Supply Chain AI module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════════
# Supplier Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class SupplierCreate(BaseModel):
    """Schema for creating a supplier."""
    name: str = Field(..., max_length=255)
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    product_categories: Optional[List[str]] = None
    lead_time_days: int = 7
    cost_per_unit: float = 0.0
    capacity: int = 1000
    quality_rating: float = 5.0
    contract_expiry: Optional[str] = None


class SupplierUpdate(BaseModel):
    """Schema for updating a supplier."""
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    product_categories: Optional[List[str]] = None
    lead_time_days: Optional[int] = None
    cost_per_unit: Optional[float] = None
    capacity: Optional[int] = None
    quality_rating: Optional[float] = None
    contract_expiry: Optional[str] = None


class SupplierResponse(BaseModel):
    """Supplier response schema."""
    id: uuid.UUID
    name: str
    contact_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    location: Optional[str]
    country: Optional[str]
    product_categories: Optional[List[str]]
    lead_time_days: int
    cost_per_unit: float
    capacity: int
    quality_rating: float
    reliability_score: float
    contract_expiry: Optional[str]
    risk_score: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Warehouse Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class WarehouseCreate(BaseModel):
    """Schema for creating a warehouse."""
    name: str = Field(..., max_length=255)
    location: str = Field(..., max_length=255)
    capacity: int = 10000
    storage_cost_per_unit: float = 1.0
    manager: Optional[str] = None


class WarehouseResponse(BaseModel):
    """Warehouse response schema."""
    id: uuid.UUID
    name: str
    location: str
    capacity: int
    utilization: float
    storage_cost_per_unit: float
    efficiency_score: float
    incoming_shipments: int
    outgoing_shipments: int
    manager: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Inventory Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class InventoryCreate(BaseModel):
    """Schema for creating inventory item."""
    warehouse_id: uuid.UUID
    product_name: str = Field(..., max_length=255)
    product_sku: str = Field(..., max_length=128)
    category: str = "general"
    current_stock: int = 0
    reorder_level: int = 100
    safety_stock: int = 50
    max_stock: int = 5000
    unit_cost: float = 0.0
    expiry_date: Optional[str] = None


class InventoryResponse(BaseModel):
    """Inventory response schema."""
    id: uuid.UUID
    warehouse_id: uuid.UUID
    product_name: str
    product_sku: str
    category: str
    current_stock: int
    reorder_level: int
    safety_stock: int
    max_stock: int
    incoming_stock: int
    reserved_stock: int
    available_stock: int
    unit_cost: float
    turnover_rate: float
    expiry_date: Optional[str]
    status: str  # normal, low_stock, overstock, dead_stock, fast_moving, slow_moving
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryUpdate(BaseModel):
    """Schema for updating inventory."""
    current_stock: Optional[int] = None
    reorder_level: Optional[int] = None
    safety_stock: Optional[int] = None
    max_stock: Optional[int] = None
    unit_cost: Optional[float] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Shipment Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class ShipmentCreate(BaseModel):
    """Schema for creating a shipment."""
    supplier_id: uuid.UUID
    warehouse_id: uuid.UUID
    shipment_number: str = Field(..., max_length=128)
    product_name: str = Field(..., max_length=255)
    quantity: int = 0
    vehicle_info: Optional[str] = None
    route: Optional[str] = None
    origin: str = Field(..., max_length=255)
    destination: str = Field(..., max_length=255)
    distance_km: float = 0.0
    fuel_cost: float = 0.0
    transport_cost: float = 0.0


class ShipmentResponse(BaseModel):
    """Shipment response schema."""
    id: uuid.UUID
    supplier_id: uuid.UUID
    warehouse_id: uuid.UUID
    shipment_number: str
    status: str
    product_name: str
    quantity: int
    vehicle_info: Optional[str]
    route: Optional[str]
    origin: str
    destination: str
    distance_km: float
    estimated_arrival: Optional[datetime]
    actual_arrival: Optional[datetime]
    fuel_cost: float
    transport_cost: float
    route_efficiency: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShipmentUpdate(BaseModel):
    """Schema for updating shipment status."""
    status: Optional[str] = None
    actual_arrival: Optional[datetime] = None
    notes: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class RiskResponse(BaseModel):
    """Supply chain risk response."""
    id: uuid.UUID
    risk_type: str
    title: str
    description: str
    severity: str
    probability: float
    risk_score: float
    business_impact: Optional[str]
    priority: str
    affected_entity_type: Optional[str]
    affected_entity_id: Optional[str]
    status: str
    mitigation: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class RiskPrediction(BaseModel):
    """AI risk prediction."""
    risk_type: str
    probability: float
    confidence: float
    timeframe: str
    factors: List[str]
    mitigation: str


class RiskPredictionResponse(BaseModel):
    """Risk prediction response."""
    predictions: List[RiskPrediction]
    overall_risk_level: str
    generated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Alert Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class AlertResponse(BaseModel):
    """Supply chain alert response."""
    id: uuid.UUID
    title: str
    description: str
    severity: str
    alert_type: str
    suggested_action: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Health Score Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class SupplyChainHealthResponse(BaseModel):
    """Supply chain health score response."""
    overall_score: float = Field(ge=0, le=100)
    category_scores: Dict[str, float]
    trend: str  # improving, declining, stable
    suggestions: List[str]


# ═══════════════════════════════════════════════════════════════════════════════
# Supplier Recommendation Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class SupplierRecommendation(BaseModel):
    """Supplier recommendation."""
    supplier_id: uuid.UUID
    supplier_name: str
    score: float
    rank: int
    reasons: List[str]
    cost_score: float
    delivery_score: float
    reliability_score: float
    quality_score: float


class SupplierRecommendationResponse(BaseModel):
    """Supplier recommendation response."""
    recommendations: List[SupplierRecommendation]
    product_category: Optional[str]
    generated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Inventory Optimization Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class InventoryOptimization(BaseModel):
    """Inventory optimization recommendation."""
    product_name: str
    product_sku: str
    warehouse_name: str
    current_stock: int
    recommended_reorder: int
    optimal_safety_stock: int
    transfer_quantity: Optional[int]
    transfer_from: Optional[str]
    transfer_to: Optional[str]
    urgency: str  # immediate, soon, normal
    estimated_cost_saving: float


class InventoryOptimizationResponse(BaseModel):
    """Inventory optimization response."""
    optimizations: List[InventoryOptimization]
    optimization_score: float
    total_potential_saving: float
    generated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Route Scenario Discovery Schemas (live-news → trade-route scenarios)
# ═══════════════════════════════════════════════════════════════════════════════

class RouteRiskScenario(BaseModel):
    """A discovered trade-route scenario from live news."""

    scenario_id: str
    chokepoint_id: str
    chokepoint_name: str
    region: str
    event_type: str  # war_conflict | piracy | natural_disaster | sanctions | congestion | grounding
    event_label: str
    severity: str  # low | medium | high | critical
    risk_score: float  # 0-100
    headline: str
    source: str
    url: str
    published_at: Optional[str]
    live: bool = False  # True when sourced from a real feed, not the curated pool
    suggest_origin: Optional[str] = None  # route for "Apply & simulate"
    suggest_destination: Optional[str] = None
    summary: str


class RouteRiskResponse(BaseModel):
    """Live trade-route risk radar."""

    mode: str  # "live" | "curated"
    updated_at: datetime
    scenarios: List[RouteRiskScenario]


# ═══════════════════════════════════════════════════════════════════════════════
# Route Optimization Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class RouteOptimization(BaseModel):
    """Route optimization result."""
    origin: str
    destination: str
    optimized_route: str
    estimated_time_hours: float
    distance_km: float
    fuel_saved: float
    cost_saved: float
    efficiency_improvement: float


class RouteOptimizationResponse(BaseModel):
    """Route optimization response."""
    routes: List[RouteOptimization]
    total_fuel_saved: float
    total_cost_saved: float
    generated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario Analysis Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioRequest(BaseModel):
    """Scenario simulation request."""
    scenario_type: str = Field(
        ...,
        description="supplier_failure, warehouse_closure, demand_increase, fuel_price_increase, "
                    "transportation_strike, port_congestion, inventory_shortage, natural_disaster"
    )
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ScenarioImpact(BaseModel):
    """Scenario impact on supply chain."""
    inventory_impact: str
    delivery_impact: str
    revenue_impact: str
    operations_impact: str
    lead_time_impact: str
    risk_score_change: float
    severity: str


class ScenarioResponse(BaseModel):
    """Scenario simulation response."""
    id: uuid.UUID
    scenario_type: str
    name: str
    impact: ScenarioImpact
    recommendations: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Optimization Engine Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class OptimizationRecommendation(BaseModel):
    """Optimization recommendation."""
    category: str  # logistics, supplier, warehouse, inventory, procurement
    title: str
    description: str
    expected_saving: float
    priority: str
    implementation_effort: str


class OptimizationResponse(BaseModel):
    """Optimization engine response."""
    recommendations: List[OptimizationRecommendation]
    total_potential_saving: float
    efficiency_improvement: float
    generated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Supply Chain Agent Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class SupplyChainQuery(BaseModel):
    """Natural language supply chain question."""
    question: str = Field(..., min_length=3, max_length=2000)


class SupplyChainAgentResponse(BaseModel):
    """Supply chain agent response."""
    answer: str
    context_used: Dict[str, Any]
    confidence: float


# ═══════════════════════════════════════════════════════════════════════════════
# Explainable AI Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class ExplanationResult(BaseModel):
    """Explainable AI output."""
    why: str
    factors: List[str]
    expected_benefits: List[str]
    possible_risks: List[str]
    assumptions: List[str]
    confidence: float


# ═══════════════════════════════════════════════════════════════════════════════
# Report Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class SupplyChainReportRequest(BaseModel):
    """Report generation request."""
    report_type: str = "full"  # full, supplier, inventory, warehouse, logistics, risk, optimization
    include_charts: bool = True


class SupplyChainReportResponse(BaseModel):
    """Report generation response."""
    report_id: str
    download_url: str
    generated_at: datetime
    pages: int
    report_type: str


# ═══════════════════════════════════════════════════════════════════════════════
# Warehouse Utilization Report
# ═══════════════════════════════════════════════════════════════════════════════

class WarehouseUtilizationReport(BaseModel):
    """Warehouse utilization report."""
    warehouse_id: uuid.UUID
    warehouse_name: str
    capacity: int
    current_utilization: float
    utilization_trend: str
    storage_cost: float
    efficiency_score: float
    recommendations: List[str]
