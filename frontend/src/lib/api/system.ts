import { apiClient } from "./client";

export interface SeedCounts {
  simulations: number;
  insights: number;
  suppliers: number;
  warehouses: number;
  inventory: number;
  shipments: number;
}

export interface SeedSummary {
  skipped: boolean;
  reason?: string;
  twin?: { id: string; name: string };
  counts?: SeedCounts;
}

export interface SeedStatus {
  has_data: boolean;
  twin_count: number;
}

/** GET /system/seed/status — whether the database already has data */
export async function getSeedStatus(): Promise<SeedStatus> {
  const res = await apiClient.get<SeedStatus>("/system/seed/status");
  return res.data;
}

/**
 * POST /system/seed — apply a dataset to the database.
 * Pass `data: null` to restore the built-in demo dataset.
 */
export async function applySeedData(data: unknown | null, force: boolean): Promise<SeedSummary> {
  const res = await apiClient.post<SeedSummary>("/system/seed", { data: data ?? null, force });
  return res.data;
}

/** GET /system/seed/template — the custom-data template for download */
export async function getSeedTemplate(): Promise<Record<string, unknown>> {
  const res = await apiClient.get<Record<string, unknown>>("/system/seed/template");
  return res.data;
}
