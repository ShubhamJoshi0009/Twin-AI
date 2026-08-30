import { apiClient } from "./client";
import type { NewsItem } from "@/lib/types";

/** GET /news?q=... — real-time market headlines (GDELT, curated fallback). */
export async function fetchNews(query: string, limit = 8): Promise<NewsItem[]> {
  const res = await apiClient.get<NewsItem[]>("/news", { params: { q: query, limit } });
  return res.data;
}
