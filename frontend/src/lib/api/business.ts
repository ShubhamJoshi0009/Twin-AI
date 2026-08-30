import { apiClient } from "./client";
import type {
  AgentResponse,
  BusinessData,
  ChecklistAuditSummary,
  DigitalTwin,
  HealthScore,
  Insight,
  Prediction,
  Report,
  Simulation,
  SourceChecklistOverviewResponse,
  SourceChecklistResponse,
  StrategyResponse,
  TimelineEntry,
  WhatIfResponse,
  WhatIfScenario,
} from "@/lib/types";

/**
 * The backend wraps prediction metrics under `predictions.predictions` and
 * names the customer metric `customer_growth`, while the frontend consumes a
 * flat `predictions` map keyed `customers`. Normalize so live backend data and
 * demo data share one shape (no-op when the payload is already flat).
 */
function normalizeSimulation(sim: Simulation): Simulation {
  const raw = sim.predictions as Record<string, unknown>;
  const nested = raw.predictions;
  if (!nested || typeof nested !== "object") return sim;
  const { customer_growth, ...rest } = nested as Record<string, Prediction>;
  const customers = customer_growth ?? rest.customers;
  return { ...sim, predictions: { ...rest, customers } };
}

/** POST /digital-twins — create a digital twin */
export async function createTwin(data: BusinessData): Promise<DigitalTwin> {
  const res = await apiClient.post<DigitalTwin>("/digital-twins", data);
  return res.data;
}

/** GET /digital-twins — list all twins */
export async function listTwins(): Promise<DigitalTwin[]> {
  const res = await apiClient.get<DigitalTwin[]>("/digital-twins");
  return res.data;
}

/** GET /digital-twins/{id} */
export async function getTwin(id: string): Promise<DigitalTwin> {
  const res = await apiClient.get<DigitalTwin>(`/digital-twins/${id}`);
  return res.data;
}

/** PUT /digital-twins/{id} */
export async function updateTwin(id: string, data: BusinessData): Promise<DigitalTwin> {
  const res = await apiClient.put<DigitalTwin>(`/digital-twins/${id}`, data);
  return res.data;
}

/** DELETE /digital-twins/{id} */
export async function deleteTwin(id: string): Promise<void> {
  await apiClient.delete(`/digital-twins/${id}`);
}

/** GET /digital-twins/{id}/sources — data-source checklist for a profile */
export async function getSourceChecklist(id: string): Promise<SourceChecklistResponse> {
  const res = await apiClient.get<SourceChecklistResponse>(`/digital-twins/${id}/sources`);
  return res.data;
}

/** GET /digital-twins/sources/overview — per-profile coverage across all twins */
export async function getSourcesOverview(): Promise<SourceChecklistOverviewResponse> {
  const res = await apiClient.get<SourceChecklistOverviewResponse>("/digital-twins/sources/overview");
  return res.data;
}

/** POST /digital-twins/sources/refresh — re-audit every profile now */
export async function refreshSources(): Promise<ChecklistAuditSummary> {
  const res = await apiClient.post<ChecklistAuditSummary>("/digital-twins/sources/refresh");
  return res.data;
}

/** PUT /digital-twins/{id}/sources — persist saved completion state */
export async function saveSourceChecklist(
  id: string,
  completions: Record<string, boolean>
): Promise<SourceChecklistResponse> {
  const res = await apiClient.put<SourceChecklistResponse>(`/digital-twins/${id}/sources`, {
    completions,
  });
  return res.data;
}

export type ReportExportFormat = "pdf" | "html" | "csv" | "markdown" | "json";

/** GET /digital-twins/{id}/sources/export — download the profile report */
export async function exportSourceChecklist(
  id: string,
  format: ReportExportFormat = "markdown"
): Promise<Blob> {
  const res = await apiClient.get<Blob>(`/digital-twins/${id}/sources/export`, {
    params: { format },
    responseType: "blob",
  });
  return res.data;
}

/** POST /simulations/{id}/run — run a decision simulation */
export async function runSimulation(
  twinId: string,
  decisionType: string,
  decisionParams: Record<string, unknown> = {}
): Promise<Simulation> {
  const res = await apiClient.post<Simulation>(`/simulations/${twinId}/run`, {
    decision_type: decisionType,
    decision_params: decisionParams,
  });
  return normalizeSimulation(res.data);
}

/** POST /simulations/{id}/compare — what-if scenario comparison */
export async function compareScenarios(twinId: string, scenarios: WhatIfScenario[]): Promise<WhatIfResponse> {
  const res = await apiClient.post<WhatIfResponse>(`/simulations/${twinId}/compare`, { scenarios });
  return res.data;
}

/** GET /simulations/decision-types — available decisions */
export async function getDecisionTypes(): Promise<{ decision_types: Array<{ value: string; label: string; description: string }> }> {
  const res = await apiClient.get("/simulations/decision-types");
  return res.data;
}

/** GET /health/{id} — business health score */
export async function getHealth(id: string): Promise<HealthScore> {
  const res = await apiClient.get<HealthScore>(`/health/${id}`);
  return res.data;
}

/** POST /strategies/{id}/generate */
export async function generateStrategies(twinId: string): Promise<StrategyResponse> {
  const res = await apiClient.post<StrategyResponse>(`/strategies/${twinId}/generate`);
  return res.data;
}

/** POST /agent/{id}/ask */
export async function askAgent(twinId: string, question: string): Promise<AgentResponse> {
  const res = await apiClient.post<AgentResponse>(`/agent/${twinId}/ask`, { question });
  return res.data;
}

/** POST /insights/{id}/generate — regenerate insights */
export async function generateInsights(twinId: string): Promise<Insight[]> {
  const res = await apiClient.post<Insight[]>(`/insights/${twinId}/generate`);
  return res.data;
}

/** GET /insights/{id} — stored insights */
export async function getInsights(twinId: string): Promise<Insight[]> {
  const res = await apiClient.get<Insight[]>(`/insights/${twinId}`);
  return res.data;
}

/** POST /reports/{id}/generate */
export async function generateReport(
  twinId: string,
  opts: { include_simulations?: boolean; include_insights?: boolean; include_strategies?: boolean } = {}
): Promise<Report> {
  const res = await apiClient.post<Report>(`/reports/${twinId}/generate`, opts);
  return res.data;
}

/** GET /timeline/{id} — simulation history */
export async function getTimeline(twinId: string): Promise<TimelineEntry[]> {
  const res = await apiClient.get<TimelineEntry[]>(`/timeline/${twinId}`);
  return res.data;
}

/** GET /timeline/{id}/{simId} — replay a single simulation */
export async function getSimulation(twinId: string, simId: string): Promise<Simulation> {
  const res = await apiClient.get<Simulation>(`/timeline/${twinId}/${simId}`);
  return normalizeSimulation(res.data);
}
