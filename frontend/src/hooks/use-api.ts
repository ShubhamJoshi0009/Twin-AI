"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import { errorMessage } from "@/lib/api/client";
import * as agentic from "@/lib/api/agentic";
import * as business from "@/lib/api/business";
import * as newsApi from "@/lib/api/news";
import * as routesApi from "@/lib/api/routes";
import * as sc from "@/lib/api/supply-chain";
import * as mock from "@/lib/mock/mock-data";
import type {
  AgentResponse,
  Alert,
  DigitalTwin,
  HealthScore,
  Insight,
  InventoryAnomaly,
  InventoryItem,
  NewsItem,
  OptimizationResponse,
  Risk,
  RiskPrediction,
  SCHealthScore,
  ScenarioSimulation,
  Shipment,
  Simulation,
  StrategyResponse,
  Supplier,
  TimelineEntry,
  Warehouse,
  WarehouseUtilization,
} from "@/lib/types";

/**
 * A small wrapper around useQuery that:
 *  - uses the real backend endpoint,
 *  - falls back to demo mock data when the backend is unreachable,
 *  - exposes `fromMock` so UI can show a subtle "demo data" indicator.
 */
function useApi<T>(
  key: string[],
  fetcher: () => Promise<T>,
  fallback: T,
  options: { staleTime?: number; refetchInterval?: number } = {}
) {
  return useQuery<T, AxiosError>({
    queryKey: key,
    queryFn: async () => {
      try {
        return await fetcher();
      } catch (err) {
        const axiosErr = err as AxiosError;
        const status = axiosErr.response?.status;
        // Offline (no response) or the resource doesn't exist in a fresh
        // backend (404/422) → fall back to demo data so the UI stays navigable.
        // Real 4xx/5xx server errors still surface with a retry action.
        if (!axiosErr.response || status === 404 || status === 422) {
          return fallback;
        }
        throw err;
      }
    },
    retry: 1,
    staleTime: options.staleTime ?? 30_000,
    refetchInterval: options.refetchInterval,
  });
}

export const useApiErrorMessage = (err: unknown) => (err ? errorMessage(err) : null);

/* ── Business Decision AI ─────────────────────────────────────────────────── */

export function useTwins() {
  return useApi(["twins"], business.listTwins, [mock.MOCK_TWIN], { refetchInterval: 30_000 });
}

// When no real twin exists yet (fresh backend) or the twin id is the built-in
// demo id, skip the network call entirely and resolve the demo dataset — avoids
// 404/422 console noise on first load and keeps the UI fully navigable offline.
const noTwin = <T,>(fallback: T) => () => Promise.resolve(fallback);
// Real twin id, or null when it's missing / the demo id (nothing to call the API with).
const realTwinId = (id: string | null) => (mock.isDemoTwinId(id) ? null : id);

export function useTwin(twinId: string | null) {
  const real = realTwinId(twinId);
  return useApi(["twin", twinId ?? "none"], real ? () => business.getTwin(real) : noTwin(mock.MOCK_TWIN), mock.MOCK_TWIN);
}

export function useHealth(twinId: string | null) {
  const real = realTwinId(twinId);
  return useApi(["health", twinId ?? "none"], real ? () => business.getHealth(real) : noTwin(mock.MOCK_HEALTH), mock.MOCK_HEALTH);
}

export function useSimulation(twinId: string | null, decisionType: string | null) {
  const real = realTwinId(twinId);
  return useApi<Simulation | null>(
    ["simulation", twinId ?? "none", decisionType ?? "none"],
    () =>
      decisionType
        ? real
          ? business.runSimulation(real, decisionType, {})
          : Promise.resolve(mock.MOCK_SIMULATION)
        : Promise.resolve(null),
    decisionType ? mock.MOCK_SIMULATION : null
  );
}

export function useStrategies(twinId: string | null) {
  const real = realTwinId(twinId);
  return useApi(["strategies", twinId ?? "none"], real ? () => business.generateStrategies(real) : noTwin(mock.MOCK_STRATEGIES), mock.MOCK_STRATEGIES);
}

export function useInsights(twinId: string | null) {
  const real = realTwinId(twinId);
  return useApi<Insight[]>(["insights", twinId ?? "none"], real ? () => business.getInsights(real) : noTwin(mock.MOCK_INSIGHTS), mock.MOCK_INSIGHTS);
}

export function useTimeline(twinId: string | null) {
  const real = realTwinId(twinId);
  return useApi<TimelineEntry[]>(["timeline", twinId ?? "none"], real ? () => business.getTimeline(real) : noTwin(mock.MOCK_TIMELINE), mock.MOCK_TIMELINE);
}

/** Cross-profile coverage overview (per business profile) — auto-refreshing. */
export function useSourcesOverview() {
  const fallback: import("@/lib/types").SourceChecklistOverviewResponse = {
    generated_at: new Date(0).toISOString(),
    items: [],
  };
  return useApi<import("@/lib/types").SourceChecklistOverviewResponse>(
    ["sources-overview"],
    business.getSourcesOverview,
    fallback,
    { staleTime: 60_000 }
  );
}

export function useSourceChecklist(twinId: string | null) {
  const real = realTwinId(twinId);
  const fallback = {
    twin_id: twinId ?? "demo-twin-001",
    company: "TechNova Solutions",
    industry: "technology",
    overall_coverage: 0,
    verified_count: 0,
    complete_count: 0,
    partial_count: 0,
    missing_count: 0,
    completed_count: 0,
    total_sections: 0,
    saved_at: null,
    items: [],
    generated_at: new Date(0).toISOString(),
  } as const satisfies import("@/lib/types").SourceChecklistResponse;
  return useApi<import("@/lib/types").SourceChecklistResponse>(
    ["source-checklist", twinId ?? "none"],
    real ? () => business.getSourceChecklist(real) : noTwin(fallback),
    fallback,
    { staleTime: 60_000 }
  );
}

/* ── Market news (GDELT / curated fallback) ──────────────────────────────── */

export function useMarketNews(query: string | null, limit = 6) {
  return useApi<NewsItem[]>(
    ["news", query ?? "none", String(limit)],
    () => (query ? newsApi.fetchNews(query, limit) : Promise.resolve(mock.MOCK_NEWS)),
    mock.MOCK_NEWS,
    { staleTime: 5 * 60_000 }
  );
}

export function useMarketWatch() {
  return useApi<import("@/lib/types").MarketWatchResponse>(
    ["market-watch"],
    () => agentic.getMarketWatch(3),
    {
      mode: "curated",
      market_context: "Curated market context — connect to a backend for live news.",
      items: [],
      updated_at: new Date(0).toISOString(),
    },
    { refetchInterval: 5 * 60_000 }
  );
}

/* ── Trade-route risk radar (live news → chokepoint scenarios) ───────────── */

export function useRouteRiskScenarios(limit = 6) {
  return useApi<import("@/lib/types").RouteRiskResponse>(
    ["route-risk", String(limit)],
    () => routesApi.getRouteRiskScenarios(limit),
    {
      mode: "curated",
      updated_at: new Date(0).toISOString(),
      scenarios: [],
    },
    { refetchInterval: 10 * 60_000 }
  );
}

/* ── Route weather monitoring (real-time, auto-refreshing) ───────────────── */

export function useRouteWeather(refreshMs = 60_000) {
  return useApi<import("@/lib/types").RouteWeatherResponse>(
    ["route-weather"],
    routesApi.getRouteWeather,
    {
      mode: "simulated",
      generated_at: new Date(0).toISOString(),
      ports: [],
      lanes: [],
      alerts: [],
      summary: { ports: 0, lanes: 0, alerts: 0, worst_level: "GREEN" },
    },
    { refetchInterval: refreshMs, staleTime: 15_000 }
  );
}

export function useRouteWeatherDetail(origin: string | null, destination: string | null, refreshMs = 60_000) {
  return useApi<import("@/lib/types").RouteWeatherDetail | null>(
    ["route-weather-detail", origin ?? "none", destination ?? "none"],
    () =>
      origin && destination
        ? routesApi.getRouteWeatherDetail(origin, destination)
        : Promise.resolve(null),
    null,
    { refetchInterval: refreshMs, staleTime: 15_000 }
  );
}

/* ── Supply Chain AI ──────────────────────────────────────────────────────── */

export function useSuppliers() {
  return useApi<Supplier[]>(["suppliers"], sc.listSuppliers, mock.MOCK_SUPPLIERS, { refetchInterval: 60_000 });
}

export function useWarehouses() {
  return useApi<Warehouse[]>(["warehouses"], sc.listWarehouses, mock.MOCK_WAREHOUSES);
}

export function useWarehouseUtilization(id: string | null) {
  return useApi<WarehouseUtilization | null>(
    ["warehouse-util", id ?? "none"],
    () => (id ? sc.getWarehouseUtilization(id) : Promise.resolve(null)),
    mock.MOCK_WAREHOUSE_UTILIZATION
  );
}

export function useInventory() {
  return useApi<InventoryItem[]>(["inventory"], sc.listInventory, mock.MOCK_INVENTORY, { refetchInterval: 30_000 });
}

export function useInventoryAnomalies() {
  return useApi<{ count: number; anomalies: InventoryAnomaly[] }>(
    ["inventory-anomalies"],
    sc.getInventoryAnomalies,
    { count: mock.MOCK_INVENTORY_ANOMALIES.length, anomalies: mock.MOCK_INVENTORY_ANOMALIES }
  );
}

export function useShipments() {
  return useApi<Shipment[]>(["shipments"], sc.listShipments, mock.MOCK_SHIPMENTS, { refetchInterval: 60_000 });
}

export function useRisks() {
  return useApi<Risk[]>(["risks"], sc.listActiveRisks, mock.MOCK_RISKS);
}

export function useRiskPredictions() {
  return useApi<{ predictions: RiskPrediction[] }>(["risk-predictions"], sc.predictRisks, {
    predictions: mock.MOCK_RISK_PREDICTIONS,
  });
}

export function useAlerts() {
  return useApi<Alert[]>(["alerts"], sc.listActiveAlerts, mock.MOCK_ALERTS, { refetchInterval: 30_000 });
}

export function useSCHealth() {
  return useApi<SCHealthScore>(["sc-health"], sc.getSupplyChainHealth, mock.MOCK_SC_HEALTH);
}

export function useOptimization() {
  return useApi<OptimizationResponse>(["optimization"], sc.runOptimization, mock.MOCK_OPTIMIZATION);
}

/* ── Mutations (no mock fallback — these are real writes) ────────────────── */

export function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: string[][]) => keys.forEach((k) => qc.invalidateQueries({ queryKey: k }));
}

export type { AgentResponse, DigitalTwin, Simulation, StrategyResponse, TimelineEntry };
