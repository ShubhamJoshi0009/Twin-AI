/* ─────────────────────────────────────────────────────────────────────────────
 * Types mirroring the Business Twin AI backend (FastAPI) response schemas.
 * Kept aligned with business_twin_ai/core/schemas and supply_chain/schemas.
 * ───────────────────────────────────────────────────────────────────────────── */

// ── Business Decision AI ─────────────────────────────────────────────────────

export interface BusinessData {
  name: string;
  industry: string;
  description?: string | null;
  revenue: number;
  expenses: number;
  profit?: number;
  cash_flow?: number;
  customers: number;
  employees: number;
  products?: Record<string, unknown> | null;
  sales: number;
  marketing_budget: number;
  pricing?: Record<string, number> | null;
  inventory_summary?: Record<string, unknown> | null;
  warehouses?: Record<string, unknown> | null;
  competitors?: Record<string, unknown> | null;
  market_share: number;
  kpis?: Record<string, number> | null;
}

export interface DigitalTwin extends BusinessData {
  id: string;
  business_health_score: number;
  created_at: string;
  updated_at: string;
}

// ── Source Checklist (business profile data audit) ──────────────────────────

export type SourceStatus = "verified" | "complete" | "partial" | "missing";
export type SourceCategory =
  | "user-provided"
  | "financial"
  | "operational"
  | "market"
  | "ai-generated"
  | "real-time";

export interface SourceCheck {
  field: string;
  label: string;
  present: boolean;
  value: string;
}

export interface SourceChecklistItem {
  source_id: string;
  name: string;
  category: SourceCategory;
  owner: string;
  status: SourceStatus;
  coverage_score: number;
  checks: SourceCheck[];
  last_updated?: string | null;
  notes: string;
  /** User-marked completion (persisted via PUT /sources). */
  completed: boolean;
  /** True when completion was explicitly saved, not auto-derived. */
  saved: boolean;
}

export interface SourceChecklistResponse {
  twin_id: string;
  company: string;
  industry: string;
  overall_coverage: number;
  verified_count: number;
  complete_count: number;
  partial_count: number;
  missing_count: number;
  completed_count: number;
  total_sections: number;
  saved_at?: string | null;
  items: SourceChecklistItem[];
  generated_at: string;
}

/** One summary row in the cross-profile coverage overview. */
export interface SourceChecklistOverviewItem {
  twin_id: string;
  company: string;
  industry: string;
  overall_coverage: number;
  completed_count: number;
  total_sections: number;
  verified_count: number;
  complete_count: number;
  partial_count: number;
  missing_count: number;
  regressed: boolean;
  last_audited_at?: string | null;
}

export interface SourceChecklistOverviewResponse {
  generated_at: string;
  items: SourceChecklistOverviewItem[];
}

export interface ChecklistAuditSummary {
  audited: number;
  regressed: string[];
  ran_at: string;
}

export interface DecisionRequest {
  decision_type: string;
  decision_params?: Record<string, unknown>;
}

export interface Prediction {
  current: number;
  predicted: number;
  change_percent: number;
  direction: "up" | "down" | "neutral";
}

export interface Scenario {
  label: "Best Case" | "Expected Case" | "Worst Case";
  revenue: number;
  profit: number;
  roi: number;
  demand: number;
  risk: number;
  probability: number;
  explanation: string;
}

export interface ConfidenceResult {
  score: number;
  level: "High" | "Medium" | "Low";
  reason: string;
  supporting_factors: string[];
}

export interface RecommendationResult {
  recommendation: string;
  expected_improvement: string;
  reasoning: string;
  business_impact: string;
  alternative_strategy: string;
}

export interface ExplanationResult {
  why: string;
  factors: string[];
  positive_factors: string[];
  negative_factors: string[];
  assumptions: string[];
  limitations: string[];
}

export interface Simulation {
  id: string;
  twin_id: string;
  decision_type: string;
  decision_params: Record<string, unknown>;
  predictions: Record<string, Prediction>;
  scenarios: Scenario[];
  confidence: ConfidenceResult;
  recommendation: RecommendationResult;
  explanation: ExplanationResult;
  created_at: string;
}

export interface HealthScore {
  overall_score: number;
  category_scores: Record<string, number>;
  trend: "improving" | "declining" | "stable";
  suggestions: string[];
}

export interface Strategy {
  strategy_type: string;
  title: string;
  description: string;
  expected_impact: Record<string, unknown>;
  reasoning: string;
  priority: "high" | "medium" | "low";
}

export interface StrategyResponse {
  strategies: Strategy[];
  summary: string;
}

export interface AgentResponse {
  answer: string;
  context_used: Record<string, unknown>;
  confidence: number;
}

export interface Insight {
  id: string;
  twin_id?: string;
  insight_type: string;
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
  data?: Record<string, unknown> | null;
  created_at: string;
}

export interface WhatIfScenario {
  name: string;
  decision_type: string;
  decision_params?: Record<string, unknown>;
}

export interface WhatIfComparison {
  name: string;
  decision_type: string;
  revenue: number;
  profit: number;
  roi: number;
  risk: number;
  customer_growth: number;
  health_score: number;
}

export interface NewsItem {
  title: string;
  url: string;
  source: string;
  published_at?: string | null;
  language?: string | null;
  country?: string | null;
  sentiment?: string | null;
}

export interface WhatIfResponse {
  comparisons: WhatIfComparison[];
  recommendation: string;
  winner: string;
  news?: NewsItem[];
  market_context?: string;
  news_query?: string;
}

// ── Route Diversion Simulator ───────────────────────────────────────────────

export interface RoutePort {
  id: string;
  name: string;
  lat: number;
  lng: number;
  region: string;
}

export interface RouteSegmentInfo {
  id: string;
  from: string;
  to: string;
  label: string;
  chokepoint: string | null;
  distance_km: number;
}

export interface ChokepointInfo {
  id: string;
  name: string;
  region: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  risk_multiplier: number;
  /** "maritime" (sea lane) or "land" (rail / land corridor). */
  kind?: "maritime" | "land";
  /** Recommended optimal alternative route when this chokepoint is blocked. */
  solution?: string | null;
}

export interface RouteNetwork {
  ports: RoutePort[];
  segments: RouteSegmentInfo[];
  chokepoints: ChokepointInfo[];
}

export interface RouteSegmentStep {
  from: string;
  to: string;
  lane: string;
  chokepoint: string | null;
  distance_km: number;
  risk: number;
}

export interface RoutePathPayload {
  segments: RouteSegmentStep[];
  port_ids: string[];
  total_km: number;
  days: number;
  cost: number;
  risk: number;
  chokepoints: string[];
}

export interface RouteEvent {
  id: string;
  label: string;
  icon: string;
  severity: string;
}

export interface BlockedChokepoint {
  id: string;
  name: string;
  region: string;
  description: string;
  severity: string;
  risk_multiplier: number;
  kind?: "maritime" | "land";
  solution?: string | null;
}

export interface RouteImpact {
  extra_km: number;
  extra_days: number;
  extra_cost: number;
  risk_baseline: number;
  risk_diverted: number;
}

export interface RouteSimulation {
  simulation_id: string;
  origin: RoutePort;
  destination: RoutePort;
  event: RouteEvent;
  status: "clear" | "diverted" | "no_alternative";
  blocked_chokepoints: BlockedChokepoint[];
  impact: RouteImpact;
  baseline: RoutePathPayload;
  diverted: RoutePathPayload | null;
  recommendation: string;
  news?: NewsItem[];
}

export interface RouteRiskScenario {
  scenario_id: string;
  chokepoint_id: string;
  chokepoint_name: string;
  region: string;
  event_type: string;
  event_label: string;
  severity: Severity;
  risk_score: number;
  headline: string;
  source: string;
  url: string;
  published_at?: string | null;
  live?: boolean;
  summary: string;
  /** Suggested origin/destination for this chokepoint's lanes (for Apply & simulate). */
  suggest_origin?: string;
  suggest_destination?: string;
}

export interface RouteRiskResponse {
  mode: "live" | "curated";
  updated_at: string;
  scenarios: RouteRiskScenario[];
}

// ── Route Weather Monitoring ────────────────────────────────────────────────

export interface WeatherConditions {
  temperature_c: number;
  apparent_temperature_c: number;
  wind_speed_kmh: number;
  wind_gusts_kmh: number;
  precipitation_mm: number;
  relative_humidity: number;
  weather_code: number;
  weather_label: string;
  weather_icon: string;
  is_day: boolean;
  observed_at: string;
  source: "live" | "simulated";
}

export interface PortWeather {
  port_id: string;
  name: string;
  lat: number;
  lng: number;
  region: string;
  conditions: WeatherConditions;
  risk_score: number;
  risk_level: "GREEN" | "YELLOW" | "ORANGE" | "RED";
  summary: string;
}

export interface LaneWeather {
  from: string;
  to: string;
  lane: string;
  chokepoint: string | null;
  risk_score: number;
  risk_level: "GREEN" | "YELLOW" | "ORANGE" | "RED";
}

export interface WeatherAlert {
  location: string;
  lat?: number | null;
  lng?: number | null;
  level: "GREEN" | "YELLOW" | "ORANGE" | "RED";
  risk_score: number;
  summary: string;
}

export interface RouteWeatherResponse {
  mode: "live" | "simulated";
  generated_at: string;
  ports: PortWeather[];
  lanes: LaneWeather[];
  alerts: WeatherAlert[];
  summary: {
    ports: number;
    lanes: number;
    alerts: number;
    worst_level: "GREEN" | "YELLOW" | "ORANGE" | "RED";
  };
}

export interface RouteWeatherPoint {
  label: string;
  lat: number;
  lng: number;
  risk_score: number;
  risk_level: "GREEN" | "YELLOW" | "ORANGE" | "RED";
  summary: string;
  conditions: WeatherConditions;
}

export interface RouteWeatherDetail {
  mode: "live" | "simulated";
  generated_at: string;
  origin: string;
  destination: string;
  overall_risk_score: number;
  overall_level: "GREEN" | "YELLOW" | "ORANGE" | "RED";
  points: RouteWeatherPoint[];
  alerts: WeatherAlert[];
  recommendation: string;
}

// ── Agentic AI ───────────────────────────────────────────────────────────────

export interface AgentStep {
  agent: "orchestrator" | "financial" | "market" | "supply_chain" | "strategy";
  phase: "plan" | "tool_call" | "observe" | "synthesize" | "reflect";
  tool?: string | null;
  detail: string;
  data?: Record<string, unknown> | null;
  duration_ms?: number | null;
}

export interface ChokepointRisk {
  chokepoint: string;
  chokepoint_id: string;
  region: string;
  event: string;
  severity: Severity;
  risk_score: number;
  headline: string;
}

export interface OrchestrationResponse {
  answer: string;
  recommendation: string;
  confidence: number;
  mode: "llm" | "rule";
  steps: AgentStep[];
  news: NewsItem[];
  market_context: string;
  chokepoint_risks?: ChokepointRisk[];
}

export interface BriefingSection {
  title: string;
  body: string;
  source: string;
}

export interface BriefingResponse {
  twin_id: string;
  company: string;
  industry: string;
  generated_at: string;
  summary: string;
  health_score: number;
  sections: BriefingSection[];
  top_recommendations: string[];
  news: NewsItem[];
  mode: "llm" | "rule";
}

export interface WatchItem {
  id: string;
  name: string;
  category: "commodity" | "freight" | "geopolitical" | "index";
  trend: "up" | "down" | "volatile" | "stable";
  sentiment: "positive" | "negative" | "neutral" | "mixed";
  impact_score: number;
  direction: "positive" | "negative" | "neutral";
  rationale: string;
  news: NewsItem[];
}

export interface MarketWatchResponse {
  mode: "live" | "curated";
  market_context: string;
  items: WatchItem[];
  updated_at: string;
}

export interface TimelineEntry {
  simulation_id: string;
  decision_type: string;
  decision_params: Record<string, unknown>;
  predicted_revenue: number;
  predicted_profit: number;
  confidence_score: number;
  recommendation?: Record<string, unknown> | null;
  created_at: string;
}

export interface Report {
  report_id: string;
  download_url: string;
  generated_at: string;
  pages: number;
}

// ── Supply Chain AI ──────────────────────────────────────────────────────────

export interface Supplier {
  id: string;
  name: string;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  location: string;
  country: string;
  product_categories: string[];
  lead_time_days: number;
  cost_per_unit: number;
  capacity: number;
  quality_rating: number;
  reliability_score: number;
  contract_expiry?: string | null;
  delivery_history?: Record<string, unknown> | null;
  performance_history?: Record<string, unknown> | null;
  risk_score: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Warehouse {
  id: string;
  name: string;
  location: string;
  capacity: number;
  utilization: number;
  storage_cost_per_unit: number;
  efficiency_score: number;
  incoming_shipments: number;
  outgoing_shipments: number;
  manager?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WarehouseUtilization {
  warehouse_id: string;
  name: string;
  capacity: number;
  current_utilization: number;
  utilization_percent: number;
  available_capacity: number;
  efficiency_score: number;
}

export interface InventoryItem {
  id: string;
  warehouse_id: string;
  product_name: string;
  product_sku: string;
  category: string;
  current_stock: number;
  reorder_level: number;
  safety_stock: number;
  max_stock: number;
  incoming_stock: number;
  reserved_stock: number;
  available_stock: number;
  unit_cost: number;
  turnover_rate: number;
  expiry_date?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface InventoryAnomaly {
  type: string;
  product_name: string;
  product_sku: string;
  severity: string;
  description: string;
  current_stock: number;
  recommended_action: string;
}

export interface Shipment {
  id: string;
  supplier_id: string;
  warehouse_id: string;
  shipment_number: string;
  status: string;
  product_name: string;
  quantity: number;
  vehicle_info?: string | null;
  route?: string | null;
  origin: string;
  destination: string;
  distance_km: number;
  estimated_arrival?: string | null;
  actual_arrival?: string | null;
  fuel_cost: number;
  transport_cost: number;
  route_efficiency: number;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Risk {
  id: string;
  risk_type: string;
  title: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  probability: number;
  risk_score: number;
  business_impact: string;
  priority: "low" | "medium" | "high";
  affected_entity_type?: string | null;
  affected_entity_id?: string | null;
  status: string;
  mitigation?: string | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface RiskPrediction {
  risk_type: string;
  title: string;
  probability: number;
  predicted_impact: string;
  severity: string;
  time_horizon: string;
  recommended_action: string;
}

export interface Alert {
  id: string;
  title: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  alert_type: string;
  suggested_action: string;
  status: string;
  created_at: string;
  resolved_at?: string | null;
}

export interface SCHealthScore {
  overall_score: number;
  category_scores: Record<string, number>;
  trend: string;
  suggestions: string[];
}

export interface OptimizationRecommendation {
  category: string;
  recommendation: string;
  potential_saving: number;
  priority: string;
}

export interface OptimizationResponse {
  recommendations: OptimizationRecommendation[];
  total_potential_saving: number;
  summary: string;
}

export interface ScenarioImpact {
  inventory_impact: string;
  delivery_impact: string;
  revenue_impact: string;
  operations_impact: string;
  lead_time_impact: string;
  risk_score_change: number;
  severity: string;
}

export interface ScenarioSimulation {
  id: string;
  scenario_type: string;
  name: string;
  impact: ScenarioImpact;
  recommendations: string[];
  created_at: string;
}

export interface ScenarioTypeInfo {
  type: string;
  name: string;
}

export interface SCReport {
  report_id: string;
  report_type: string;
  download_url: string;
  generated_at: string;
}

export interface ApiError {
  detail?: string | Array<{ loc: string[]; msg: string; type: string }>;
}

// ── Frontend helpers ─────────────────────────────────────────────────────────

export type Severity = "critical" | "high" | "medium" | "low" | "info" | "warning";
export type Priority = "high" | "medium" | "low";

export interface DecisionTypeInfo {
  value: string;
  label: string;
  description: string;
  icon: string;
  params: Array<{
    key: string;
    label: string;
    type: "number" | "text" | "select";
    default?: number | string;
    min?: number;
    max?: number;
    options?: Array<{ value: string; label: string }>;
  }>;
}

