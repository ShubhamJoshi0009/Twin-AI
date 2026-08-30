import { apiClient } from "./client";
import type { BriefingResponse, MarketWatchResponse, OrchestrationResponse } from "@/lib/types";

/** POST /agentic/{twinId}/orchestrate — run the full multi-agent pipeline */
export async function orchestrate(twinId: string, question: string): Promise<OrchestrationResponse> {
  const res = await apiClient.post<OrchestrationResponse>(`/agentic/${twinId}/orchestrate`, { question });
  return res.data;
}

/** POST /agentic/{twinId}/briefing — one-shot executive briefing */
export async function generateBriefing(twinId: string): Promise<BriefingResponse> {
  const res = await apiClient.post<BriefingResponse>(`/agentic/${twinId}/briefing`);
  return res.data;
}

/** GET /market/watch — live market watch dashboard */
export async function getMarketWatch(newsLimit = 3): Promise<MarketWatchResponse> {
  const res = await apiClient.get<MarketWatchResponse>(`/market/watch`, { params: { news_limit: newsLimit } });
  return res.data;
}
