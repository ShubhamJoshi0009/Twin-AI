"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Banknote,
  Boxes,
  Fuel,
  Loader2,
  Play,
  Scale,
  Siren,
  Timer,
  Truck,
  Warehouse,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { useQuery } from "@tanstack/react-query";
import * as sc from "@/lib/api/supply-chain";
import { errorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { ScenarioSimulation, ScenarioTypeInfo, Severity } from "@/lib/types";

const SCENARIO_TYPES: Array<ScenarioTypeInfo & { icon: typeof AlertTriangle; description: string }> = [
  { type: "supplier_failure", name: "Supplier Failure", icon: AlertTriangle, description: "A key supplier stops fulfilling orders — stock drops, lead times stretch." },
  { type: "warehouse_closure", name: "Warehouse Closure", icon: Warehouse, description: "A warehouse goes offline and its inventory must be redistributed." },
  { type: "demand_increase", name: "Demand Spike", icon: Boxes, description: "Orders surge past current capacity — stockout risk and fulfillment pressure." },
  { type: "fuel_price_increase", name: "Fuel Price Increase", icon: Fuel, description: "Transportation costs spike, compressing margins on every shipment." },
  { type: "transportation_strike", name: "Transportation Strike", icon: Truck, description: "Carriers stop moving freight in a region — severe delivery disruption." },
  { type: "inventory_shortage", name: "Inventory Shortage", icon: Siren, description: "Critical stockouts across products from under-ordering or delays." },
];

const IMPACT_ROWS: Array<{ key: keyof ScenarioSimulation["impact"]; label: string; icon: typeof Scale }> = [
  { key: "inventory_impact", label: "Inventory", icon: Boxes },
  { key: "delivery_impact", label: "Delivery", icon: Truck },
  { key: "revenue_impact", label: "Revenue", icon: Banknote },
  { key: "operations_impact", label: "Operations", icon: Warehouse },
  { key: "lead_time_impact", label: "Lead time", icon: Timer },
];

export default function SCSimulatorPage() {
  const [scenarioType, setScenarioType] = useState("supplier_failure");
  const [severity, setSeverity] = useState(1.0);
  const [runId, setRunId] = useState(0);

  // `severity` in the queryKey means dragging the slider after the first run
  // live-updates the simulation — no extra clicks needed.
  const { data, isLoading, error } = useQuery({
    queryKey: ["sc-simulate", scenarioType, severity, runId],
    queryFn: () => sc.simulateScenario(scenarioType, { severity_multiplier: severity }),
    enabled: runId > 0,
    retry: 1,
  });

  const run = () => setRunId((r) => r + 1);

  const selected = SCENARIO_TYPES.find((s) => s.type === scenarioType);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Supply Chain Scenario Simulator"
        description="Stress-test your supply chain against disruptions — supplier failures, strikes, shortages, fuel spikes — and get recommended responses"
        actions={
          <Badge variant="secondary" className="gap-1.5">
            <Siren className="h-3 w-3 text-warning" /> 6 disruption scenarios
          </Badge>
        }
      />

      {/* Scenario picker */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {SCENARIO_TYPES.map((s, i) => {
          const Icon = s.icon;
          const active = scenarioType === s.type;
          return (
            <motion.button
              key={s.type}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              onClick={() => { setScenarioType(s.type); if (runId) setRunId(0); }}
              className={cn(
                "flex items-start gap-3 rounded-lg border p-4 text-left transition-all duration-200",
                active ? "border-primary/60 bg-primary/5 shadow-lg shadow-primary/10" : "border-border hover:border-primary/40 hover:bg-accent/30"
              )}
            >
              <span className={cn("mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", active ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground")}>
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold">{s.name}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{s.description}</p>
              </div>
            </motion.button>
          );
        })}
      </div>

      {/* Controls + result */}
      <div className="grid gap-4 xl:grid-cols-5">
        {/* Controls */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Scale className="h-4 w-4 text-primary" /> Scenario settings
            </CardTitle>
            <CardDescription className="text-xs">{selected?.name}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Severity multiplier</span>
                <span className="font-semibold tabular-nums">{severity.toFixed(1)}×</span>
              </div>
              <input
                type="range"
                min={0.5}
                max={2}
                step={0.1}
                value={severity}
                onChange={(e) => setSeverity(Number(e.target.value))}
                aria-label="Severity multiplier"
                className="h-2 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary"
              />
              <p className="text-[11px] text-muted-foreground">
                Scales the risk-score impact of the disruption (0.5× mild → 2× severe).
              </p>
            </div>
            <Button onClick={run} disabled={isLoading} className="w-full">
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {runId === 0 ? "Simulate scenario" : "Re-run simulation"}
            </Button>
            {error && (
              <p className="text-xs text-destructive">{errorMessage(error)}</p>
            )}
          </CardContent>
        </Card>

        {/* Result */}
        <Card className="xl:col-span-3">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="text-sm">Impact Analysis</CardTitle>
              <CardDescription className="text-xs">
                {runId === 0 ? "Run a simulation to see the impact breakdown" : `${data?.name ?? "Simulating"} · ${severity.toFixed(1)}× severity`}
              </CardDescription>
            </div>
            {data && (
              <SeverityBadge severity={(data.impact.severity ?? "medium") as Severity} />
            )}
          </CardHeader>
          <CardContent>
            {runId === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-14 text-center">
                <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                  <AlertTriangle className="h-6 w-6" />
                </motion.div>
                <p className="text-sm text-muted-foreground">Pick a disruption, tune the severity, and run the simulation.</p>
              </div>
            ) : isLoading ? (
              <div className="space-y-3 py-6">
                {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 animate-pulse rounded-lg bg-muted" />)}
              </div>
            ) : data ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
                    <AlertTriangle className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold">{data.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Risk score impact: <span className={cn("font-semibold tabular-nums", data.impact.risk_score_change > 20 ? "text-destructive" : data.impact.risk_score_change > 10 ? "text-warning" : "text-muted-foreground")}>+{data.impact.risk_score_change}</span> points
                    </p>
                  </div>
                </div>

                <div className="grid gap-2 sm:grid-cols-2">
                  {IMPACT_ROWS.map((row) => {
                    const Icon = row.icon;
                    const value = data.impact[row.key];
                    return (
                      <div key={row.key} className="rounded-lg border p-3">
                        <p className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                          <Icon className="h-3 w-3" /> {row.label}
                        </p>
                        <p className="mt-1 text-sm">{value}</p>
                      </div>
                    );
                  })}
                </div>

                <div className="rounded-lg border border-border bg-muted/40 p-4">
                  <p className="mb-2 text-sm font-semibold">Recommended response</p>
                  <ul className="space-y-1.5">
                    {data.recommendations.map((r, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" /> {r}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">No result yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
