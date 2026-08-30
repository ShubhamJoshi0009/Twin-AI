import { apiClient } from "./client";
import type {
  Alert,
  InventoryAnomaly,
  InventoryItem,
  OptimizationResponse,
  Risk,
  RiskPrediction,
  SCHealthScore,
  SCReport,
  ScenarioSimulation,
  Shipment,
  Supplier,
  Warehouse,
  WarehouseUtilization,
} from "@/lib/types";

/* ── Suppliers ─────────────────────────────────────────────────────────────── */

export async function listSuppliers(): Promise<Supplier[]> {
  const res = await apiClient.get<Supplier[]>("/supply-chain/suppliers");
  return res.data;
}

export async function getSupplier(id: string): Promise<Supplier> {
  const res = await apiClient.get<Supplier>(`/supply-chain/suppliers/${id}`);
  return res.data;
}

export async function createSupplier(data: Partial<Supplier>): Promise<Supplier> {
  const res = await apiClient.post<Supplier>("/supply-chain/suppliers", data);
  return res.data;
}

export async function updateSupplier(id: string, data: Partial<Supplier>): Promise<Supplier> {
  const res = await apiClient.put<Supplier>(`/supply-chain/suppliers/${id}`, data);
  return res.data;
}

export async function deleteSupplier(id: string): Promise<void> {
  await apiClient.delete(`/supply-chain/suppliers/${id}`);
}

/* ── Warehouses ───────────────────────────────────────────────────────────── */

export async function listWarehouses(): Promise<Warehouse[]> {
  const res = await apiClient.get<Warehouse[]>("/supply-chain/warehouses");
  return res.data;
}

export async function getWarehouse(id: string): Promise<Warehouse> {
  const res = await apiClient.get<Warehouse>(`/supply-chain/warehouses/${id}`);
  return res.data;
}

export async function createWarehouse(data: Partial<Warehouse>): Promise<Warehouse> {
  const res = await apiClient.post<Warehouse>("/supply-chain/warehouses", data);
  return res.data;
}

export async function getWarehouseUtilization(id: string): Promise<WarehouseUtilization> {
  const res = await apiClient.get<WarehouseUtilization>(`/supply-chain/warehouses/${id}/utilization`);
  return res.data;
}

/* ── Inventory ─────────────────────────────────────────────────────────────── */

export async function listInventory(): Promise<InventoryItem[]> {
  const res = await apiClient.get<InventoryItem[]>("/supply-chain/inventory");
  return res.data;
}

export async function createInventory(data: Partial<InventoryItem>): Promise<InventoryItem> {
  const res = await apiClient.post<InventoryItem>("/supply-chain/inventory", data);
  return res.data;
}

export async function getInventoryAnomalies(): Promise<{ count: number; anomalies: InventoryAnomaly[] }> {
  const res = await apiClient.get("/supply-chain/inventory/anomalies");
  return res.data;
}

export async function optimizeInventory(): Promise<{
  optimizations: Array<Record<string, unknown>>;
  optimization_score: number;
  summary: string;
}> {
  const res = await apiClient.post("/supply-chain/inventory/optimize");
  return res.data;
}

/* ── Shipments / logistics ────────────────────────────────────────────────── */

export async function listShipments(): Promise<Shipment[]> {
  const res = await apiClient.get<Shipment[]>("/supply-chain/shipments");
  return res.data;
}

export async function createShipment(data: Partial<Shipment>): Promise<Shipment> {
  const res = await apiClient.post<Shipment>("/supply-chain/shipments", data);
  return res.data;
}

export async function getDelayedShipments(): Promise<Shipment[]> {
  const res = await apiClient.get<Shipment[]>("/supply-chain/shipments/delayed");
  return res.data;
}

export async function optimizeRoutes(): Promise<{ routes: Array<Record<string, unknown>>; summary: string }> {
  const res = await apiClient.post("/supply-chain/shipments/optimize-routes");
  return res.data;
}

/* ── Risks ────────────────────────────────────────────────────────────────── */

export async function detectRisks(): Promise<Risk[]> {
  const res = await apiClient.post<Risk[]>("/supply-chain/risks/detect");
  return res.data;
}

export async function listActiveRisks(): Promise<Risk[]> {
  const res = await apiClient.get<Risk[]>("/supply-chain/risks");
  return res.data;
}

export async function predictRisks(): Promise<{ predictions: RiskPrediction[] }> {
  const res = await apiClient.post("/supply-chain/risks/predict");
  return res.data;
}

/* ── Alerts ───────────────────────────────────────────────────────────────── */

export async function generateAlerts(): Promise<Alert[]> {
  const res = await apiClient.post<Alert[]>("/supply-chain/alerts/generate");
  return res.data;
}

export async function listActiveAlerts(): Promise<Alert[]> {
  const res = await apiClient.get<Alert[]>("/supply-chain/alerts");
  return res.data;
}

/* ── Health / optimization / scenarios / reports ──────────────────────────── */

export async function getSupplyChainHealth(): Promise<SCHealthScore> {
  const res = await apiClient.get<SCHealthScore>("/supply-chain/health");
  return res.data;
}

export async function runOptimization(): Promise<OptimizationResponse> {
  const res = await apiClient.post<OptimizationResponse>("/supply-chain/optimization");
  return res.data;
}

export async function simulateScenario(
  scenarioType: string,
  parameters: Record<string, unknown> = {}
): Promise<ScenarioSimulation> {
  const res = await apiClient.post<ScenarioSimulation>("/supply-chain/scenarios/simulate", {
    scenario_type: scenarioType,
    parameters,
  });
  return res.data;
}

export async function generateSCReport(reportType = "full"): Promise<SCReport> {
  const res = await apiClient.post<SCReport>("/supply-chain/reports/generate", { report_type: reportType });
  return res.data;
}

/* ── Agent ────────────────────────────────────────────────────────────────── */

export async function askSupplyChainAgent(question: string): Promise<{ answer: string }> {
  const res = await apiClient.post("/supply-chain/agent/ask", { question });
  return res.data;
}
