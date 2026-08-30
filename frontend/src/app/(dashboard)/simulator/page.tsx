"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  FlaskConical,
  Play,
  RotateCcw,
  Trophy,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { ChartCard } from "@/components/charts/chart-card";
import { BarChartComponent } from "@/components/charts/bar-chart";
import { NewsPanel } from "@/components/simulator/news-panel";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { SkeletonGrid } from "@/components/shared/state-views";
import { RelativeTime } from "@/components/shared/relative-time";
import { useTwins } from "@/hooks/use-api";
import { errorMessage } from "@/lib/api/client";
import * as business from "@/lib/api/business";
import { DECISION_TYPES, DECISION_TYPE_MAP } from "@/lib/constants";
import { iconByName } from "@/lib/icon-map";
import type { WhatIfComparison, WhatIfResponse } from "@/lib/types";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

const MAX_DECISIONS = 5;

export default function SimulatorPage() {
  const router = useRouter();
  const { data: twins } = useTwins();
  const twinId = twins?.[0]?.id ?? null;

  const [selected, setSelected] = useState<string[]>(["increase_marketing", "launch_product"]);
  const [params, setParams] = useState<Record<string, Record<string, unknown>>>({
    increase_marketing: { percent: 20, channel: "digital" },
    launch_product: { product_name: "Apex Widget", price: 99 },
  });
  const [runId, setRunId] = useState(0);

  const toggle = (value: string) => {
    setSelected((prev) => {
      if (prev.includes(value)) return prev.filter((v) => v !== value);
      if (prev.length >= MAX_DECISIONS) {
        toast.warning(`You can compare up to ${MAX_DECISIONS} decisions at once`);
        return prev;
      }
      const info = DECISION_TYPE_MAP[value];
      const defaults = Object.fromEntries((info?.params ?? []).map((p) => [p.key, p.default ?? ""]));
      setParams((p) => ({ ...p, [value]: defaults }));
      return [...prev, value];
    });
  };

  const setParam = (decision: string, key: string, value: unknown) =>
    setParams((p) => ({ ...p, [decision]: { ...p[decision], [key]: value } }));

  const handleReset = () => {
    setSelected(["increase_marketing", "launch_product"]);
    setRunId(0);
    toast.info("Simulation reset");
  };

  const scenarios = useMemo(
    () =>
      selected.map((dt, i) => ({
        name: `${DECISION_TYPE_MAP[dt]?.label ?? dt} #${i + 1}`,
        decision_type: dt,
        decision_params: params[dt] ?? {},
      })),
    [selected, params]
  );

  const canRun = selected.length >= 1 && selected.length <= MAX_DECISIONS;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Scenario Simulator"
        description="Choose multiple decisions at once — analysis is grounded in the latest market news"
        actions={
          <>
            <Button variant="outline" size="sm" onClick={handleReset}>
              <RotateCcw /> Reset
            </Button>
            <Button size="sm" onClick={() => setRunId((k) => k + 1)} disabled={!canRun} className="gap-2">
              <Play /> Run Analysis ({selected.length})
            </Button>
          </>
        }
      />

      <div className="grid gap-4 xl:grid-cols-5">
        {/* Configuration panel */}
        <div className="space-y-4 xl:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">1 · Choose Decisions ({selected.length}/{MAX_DECISIONS})</CardTitle>
              <CardDescription>Pick 1–5 business actions to simulate side by side</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {DECISION_TYPES.map((d, i) => {
                const Icon = iconByName(d.icon);
                const active = selected.includes(d.value);
                return (
                  <motion.div
                    key={d.value}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.015 }}
                  >
                    <label
                      className={cn(
                        "flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 transition-all duration-200",
                        active ? "border-primary/50 bg-primary/10" : "border-border/60 bg-card hover:border-primary/30"
                      )}
                    >
                      <Checkbox checked={active} onCheckedChange={() => toggle(d.value)} aria-label={d.label} />
                      <Icon className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-muted-foreground")} />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium leading-tight">{d.label}</p>
                        <p className="truncate text-[11px] text-muted-foreground">{d.description}</p>
                      </div>
                      {active && <Check className="h-4 w-4 text-primary" />}
                    </label>
                  </motion.div>
                );
              })}
            </CardContent>
          </Card>

          {selected.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">2 · Configure Parameters</CardTitle>
                <CardDescription>Tune each selected decision</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <AnimatePresence>
                  {selected.map((dt) => {
                    const info = DECISION_TYPE_MAP[dt];
                    return (
                      <motion.div
                        key={dt}
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden rounded-lg border p-3"
                      >
                        <p className="mb-2 text-xs font-semibold capitalize">{info?.label ?? dt}</p>
                        {info?.params.length ? (
                          <div className="space-y-2.5">
                            {info.params.map((p) => (
                              <div key={p.key} className="space-y-1">
                                <Label htmlFor={`${dt}-${p.key}`} className="text-[11px] text-muted-foreground">{p.label}</Label>
                                {p.type === "select" ? (
                                  <Select value={String(params[dt]?.[p.key] ?? p.default ?? "")} onValueChange={(v) => setParam(dt, p.key, v)}>
                                    <SelectTrigger id={`${dt}-${p.key}`}><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      {p.options?.map((o) => (
                                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                ) : p.type === "text" ? (
                                  <Input
                                    id={`${dt}-${p.key}`}
                                    type="text"
                                    value={String(params[dt]?.[p.key] ?? p.default ?? "")}
                                    onChange={(e) => setParam(dt, p.key, e.target.value)}
                                  />
                                ) : (
                                  <Input
                                    id={`${dt}-${p.key}`}
                                    type="number"
                                    value={Number(params[dt]?.[p.key] ?? p.default ?? 0)}
                                    min={p.min}
                                    max={p.max}
                                    onChange={(e) => setParam(dt, p.key, Number(e.target.value))}
                                  />
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[11px] text-muted-foreground">Runs with defaults — no parameters required.</p>
                        )}
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Results panel */}
        <div className="space-y-4 xl:col-span-3">
          {runId === 0 ? (
            <EmptyResults />
          ) : (
            <SimulationResults key={runId} runId={runId} twinId={twinId} scenarios={scenarios} />
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyResults() {
  return (
    <Card className="flex min-h-[420px] flex-col items-center justify-center border-dashed">
      <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center gap-3 text-center">
        <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
          <FlaskConical className="h-7 w-7 text-primary" />
        </span>
        <h3 className="font-semibold">Compare decisions at once</h3>
        <p className="max-w-sm text-sm text-muted-foreground">
          Select <b>two or more decisions</b> on the left, tune their parameters, then press{" "}
          <b>Run Analysis</b> to see them side by side — with live market news grounding the verdict.
        </p>
      </motion.div>
    </Card>
  );
}

function SimulationResults({
  runId,
  twinId,
  scenarios,
}: {
  runId: number;
  twinId: string | null;
  scenarios: Array<{ name: string; decision_type: string; decision_params: Record<string, unknown> }>;
}) {
  const { data, isLoading, error, refetch } = useQuery<WhatIfResponse | null>({
    queryKey: ["simulate-compare", runId, twinId, JSON.stringify(scenarios)],
    queryFn: async () => {
      if (!twinId) return null;
      return business.compareScenarios(twinId, scenarios);
    },
    retry: 1,
  });

  if (error) {
    return (
      <Card className="p-6 text-center">
        <p className="font-semibold text-destructive">Analysis failed</p>
        <p className="mt-1 text-sm text-muted-foreground">{errorMessage(error)}</p>
        <Button className="mt-4" size="sm" variant="outline" onClick={() => refetch()}>Retry</Button>
      </Card>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="space-y-4">
        <SkeletonGrid count={3} />
        <Card className="p-6"><div className="h-40 animate-pulse rounded-md bg-muted" /></Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Winner banner */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-xl border border-primary/30 bg-gradient-to-r from-primary/15 via-violet-500/10 to-transparent p-4"
      >
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/20 text-primary">
            <Trophy className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-primary">Recommended</p>
            <p className="mt-0.5 text-sm font-semibold">{data.winner}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{data.recommendation}</p>
          </div>
        </div>
      </motion.div>

      {/* Comparison chart */}
      <ChartCard id="compare-chart" title="Projected Revenue by Decision" description="Side-by-side expected outcome" csvData={data.comparisons.map((c) => ({ name: c.name, revenue: c.revenue, profit: c.profit, roi: c.roi }))}>
        <BarChartComponent
          data={data.comparisons.map((c) => ({ name: c.name, revenue: c.revenue, profit: c.profit, roi: c.roi }))}
          xKey="name"
          series={[{ key: "revenue", name: "Revenue" }, { key: "profit", name: "Profit" }]}
          formatter={(v) => formatCurrency(v, { compact: true })}
        />
      </ChartCard>

      {/* Comparison table */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-sm">Side-by-side comparison</CardTitle>
            <CardDescription className="text-xs">{data.comparisons.length} scenarios modeled</CardDescription>
          </div>
          <Badge variant="secondary">{data.winner}</Badge>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3 text-right">Revenue</th>
                <th className="px-4 py-3 text-right">Profit</th>
                <th className="px-4 py-3 text-right">ROI</th>
                <th className="px-4 py-3 text-right">Risk</th>
                <th className="px-4 py-3 text-right">Customers</th>
              </tr>
            </thead>
            <tbody>
              {data.comparisons.map((c, i) => (
                <ComparisonRow key={c.name} c={c} winner={data.winner} index={i} />
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Market news panel */}
      <NewsPanel news={data.news ?? []} query={data.news_query} />
    </div>
  );
}

function ComparisonRow({ c, winner, index }: { c: WhatIfComparison; winner: string; index: number }) {
  const isWinner = c.name === winner;
  return (
    <motion.tr
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className={cn("border-b border-border/60 transition-colors", isWinner && "bg-primary/10")}
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          {isWinner && <Trophy className="h-3.5 w-3.5 text-primary" />}
          <span className="font-medium">{c.name}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-right font-semibold tabular-nums">{formatCurrency(c.revenue, { compact: true })}</td>
      <td className="px-4 py-3 text-right tabular-nums">{formatCurrency(c.profit, { compact: true })}</td>
      <td className="px-4 py-3 text-right tabular-nums">{formatPercent(c.roi)}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        <span className={c.risk > 60 ? "text-destructive" : c.risk > 35 ? "text-warning" : "text-success"}>{formatPercent(c.risk, 0)}</span>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{formatPercent(c.customer_growth)}</td>
    </motion.tr>
  );
}


