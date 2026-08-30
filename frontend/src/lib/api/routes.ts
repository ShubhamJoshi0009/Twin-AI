import { apiClient } from "./client";
import type {
  RouteNetwork,
  RouteRiskResponse,
  RouteSimulation,
  RouteWeatherDetail,
  RouteWeatherResponse,
} from "@/lib/types";

/** GET /supply-chain/routes/network — world shipping network for the map. */
export async function getRouteNetwork(): Promise<RouteNetwork> {
  const res = await apiClient.get<RouteNetwork>("/supply-chain/routes/network");
  return res.data;
}

/** GET /supply-chain/routes/event-types — blockage event presets. */
export async function getRouteEventTypes(): Promise<{
  events: Array<{ id: string; label: string; icon: string; severity: string }>;
}> {
  const res = await apiClient.get("/supply-chain/routes/event-types");
  return res.data;
}

/** GET /supply-chain/routes/risk-scenarios — live trade-route risk radar. */
export async function getRouteRiskScenarios(limit = 6): Promise<RouteRiskResponse> {
  const res = await apiClient.get<RouteRiskResponse>("/supply-chain/routes/risk-scenarios", {
    params: { limit },
  });
  return res.data;
}

/** POST /supply-chain/routes/simulate — simulate a voyage with blockages. */
export async function simulateRoute(payload: {
  origin: string;
  destination: string;
  blocked_chokepoints: string[];
  event_type: string;
  cargo_value?: number;
  include_news?: boolean;
}): Promise<RouteSimulation> {
  const res = await apiClient.post<RouteSimulation>("/supply-chain/routes/simulate", payload);
  return res.data;
}

/** GET /supply-chain/routes/weather — real-time weather overlay for the map. */
export async function getRouteWeather(): Promise<RouteWeatherResponse> {
  const res = await apiClient.get<RouteWeatherResponse>("/supply-chain/routes/weather");
  return res.data;
}

/** GET /supply-chain/routes/weather/route — weather + risk along a voyage. */
export async function getRouteWeatherDetail(
  origin: string,
  destination: string
): Promise<RouteWeatherDetail> {
  const res = await apiClient.get<RouteWeatherDetail>("/supply-chain/routes/weather/route", {
    params: { origin, destination },
  });
  return res.data;
}
