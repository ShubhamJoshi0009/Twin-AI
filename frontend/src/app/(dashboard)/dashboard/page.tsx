"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  Boxes,
  CircleDollarSign,
  FileText,
  FlaskConical,
  Lightbulb,
  Loader2,
  Sparkles,
  TrendingUp,
  Truck,
  Users,
  Wallet,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { QuickNav } from "@/components/shared/quick-nav";
import { RiskRadar } from "@/components/route-risk/risk-radar";
import { KPICard } from "@/components/kpi/kpi-card";
import { ChartCard } from "@/components/charts/chart-card";
import { LineAreaChart } from "@/components/charts/line-area-chart";
import { BarChartComponent } from "@/components/charts/bar-chart";
import { Gauge } from "@/components/charts/gauge";
import { RecommendationCard } from "@/components/insights/recommendation-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { SkeletonGrid, ErrorState } from "@/components/shared/state-views";
import { RelativeTime } from "@/components/shared/relative-time";
import { useAlerts, useHealth, useRouteRiskScenarios, useSCHealth, useSourcesOverview, useStrategies, useTimeline, useTwins } from "@/hooks/use-api";
import { DECISION_TYPE_MAP } from "@/lib/constants";
import { mockTimeSeries } from "@/lib/mock/mock-data";
import { formatCurrency, formatDelta, formatNumber } from "@/lib/utils";
import { toast } from "sonner";
import * as agentic from "@/lib/api/agentic";
import { errorMessage } from "@/lib/api/client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { BriefingResponse } from "@/lib/types";

export default function DashboardPage() {
  const { data: twins, isLoading: twinsLoading, error: twinsError, refetch: refetchTwins } = useTwins();
  const twinId = twins?.[0]?.id ?? null;
  const { data: health, isLoading: healthLoading } = useHealth(twinId);
  const { data: scHealth, isLoading: scHealthLoading } = useSCHealth();
  const { data: strategies, isLoading: strategiesLoading } = useStrategies(twinId);
  const { data: timeline, isLoading: timelineLoading } = useTimeline(twinId);
  const { data: alerts } = useAlerts();
  const { data: routeRisk, isLoading: radarLoading } = useRouteRiskScenarios(3);
  const { data: sourcesOverview } = useSourcesOverview();
  const [briefing, setBriefing] = useState<BriefingResponse | null>(null);
  const [briefingOpen, setBriefingOpen] = useState(false);
  const [briefingLoading, setBriefingLoading] = useState(false);

  const generateBriefing = async () => {
    if (!twinId) {
      toast.error("No digital twin found — create one first via the onboarding wizard.");
      return;
    }
    setBriefingLoading(true);
    try {
      const b = await agentic.generateBriefing(twinId);
      setBriefing(b);
      setBriefingOpen(true);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBriefingLoading(false);
    }
  };

  const twin = twins?.[0];

  // Synthetic series for trend charts (deterministic, demo-grade).
  const revenueSeries = useMemo(() => mockTimeSeries(1, 12, 190, 0.09), []);
  const profitSeries = useMemo(() => mockTimeSeries(2, 12, 46, 0.1), []);
  const cashflowSeries = useMemo(() => mockTimeSeries(3, 12, 34, 0.14), []);

  const loading = twinsLoading || healthLoading || scHealthLoading;
  const error = twinsError;

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="Executive Dashboard" description="Real-time business and supply chain performance overview" />
        <ErrorState message={error.userMessage ?? error.message} onRetry={() => refetchTwins()} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Executive Dashboard"
        description={twin ? `Live overview for ${twin.name} — ${twin.industry}` : "Real-time business and supply chain performance overview"}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={generateBriefing} disabled={briefingLoading}>
              {briefingLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4 text-chart-3" />}
              Daily Briefing
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/simulator">
                <FlaskConical /> New Simulation
              </Link>
            </Button>
            <Button asChild size="sm">
              <Link href="/chat">
                <Bot /> Ask AI
              </Link>
            </Button>
          </>
        }
      />

      <QuickNav
        items={[
          { id: "kpis", label: "KPIs", icon: <Activity className="h-3 w-3" /> },
          { id: "health", label: "Health", icon: <TrendingUp className="h-3 w-3" /> },
          { id: "charts", label: "Trends", icon: <Activity className="h-3 w-3" /> },
          { id: "risk-radar", label: "Risk Radar", icon: <AlertTriangle className="h-3 w-3" /> },
          { id: "simulations", label: "Simulations", icon: <FlaskConical className="h-3 w-3" /> },
          { id: "recommendations", label: "AI Insights", icon: <Lightbulb className="h-3 w-3" /> },
        ]}
      />

      {loading ? (
        <SkeletonGrid count={4} />
      ) : (
        <>
          {/* KPI row */}
          <div id="kpis" className="scroll-mt-28 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KPICard label="Revenue" value={formatCurrency(twin?.revenue, { compact: true })} icon={CircleDollarSign} delta={12.4} deltaLabel="vs last quarter" spark={revenueSeries.map((d) => d.value)} />
            <KPICard label="Profit" value={formatCurrency(twin?.profit, { compact: true })} icon={TrendingUp} delta={8.1} deltaLabel="net margin 24.2%" spark={profitSeries.map((d) => d.value)} sparkColor="hsl(var(--chart-2))" />
            <KPICard label="Cash Flow" value={formatCurrency(twin?.cash_flow ?? 420_000, { compact: true })} icon={Wallet} delta={5.6} deltaLabel="operating cash" spark={cashflowSeries.map((d) => d.value)} sparkColor="hsl(var(--chart-4))" />
            <KPICard label="Customers" value={formatNumber(twin?.customers, { compact: true })} icon={Users} delta={3.2} deltaLabel="active customers" />
          </div>

          {/* Health + SC row */}
          <div id="health" className="scroll-mt-28 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card className="flex flex-col items-center justify-center p-5">
              <Gauge value={health?.overall_score ?? 0} label="Business Health" sublabel={`Trend: ${health?.trend}`} />
              <div className="mt-2 flex flex-wrap justify-center gap-1.5">
                {Object.entries(health?.category_scores ?? {}).slice(0, 3).map(([k, v]) => (
                  <Badge key={k} variant="secondary" className="text-[10px] capitalize">{k}: {v}</Badge>
                ))}
              </div>
            </Card>
            <Card className="flex flex-col items-center justify-center p-5">
              <Gauge value={scHealth?.overall_score ?? 0} label="Supply Chain Health" sublabel={`Trend: ${scHealth?.trend}`} size={180} />
              <div className="mt-2 flex flex-wrap justify-center gap-1.5">
                {Object.entries(scHealth?.category_scores ?? {}).slice(0, 3).map(([k, v]) => (
                  <Badge key={k} variant="secondary" className="text-[10px] capitalize">{k}: {v}</Badge>
                ))}
              </div>
            </Card>
            <Card className="flex flex-col justify-center p-5">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Profile Source Coverage</CardTitle>
                <CardDescription className="text-xs">
                  Average data-source coverage across all business profiles
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-end justify-between">
                  <span className="text-3xl font-bold tabular-nums tracking-tight">
                    {sourcesOverview?.items.length ? Math.round(sourcesOverview.items.reduce((s, r) => s + r.overall_coverage, 0) / sourcesOverview.items.length) : 0}%
                  </span>
                  <span className="text-xs text-muted-foreground">{sourcesOverview?.items.length ?? 0} profile{(sourcesOverview?.items.length ?? 0) === 1 ? "" : "s"}</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(sourcesOverview?.items ?? []).slice(0, 4).map((row) => (
                    <Badge key={row.twin_id} variant={row.overall_coverage >= 70 ? "success" : row.overall_coverage >= 40 ? "secondary" : "destructive"} className="gap-1 !text-[10px]">
                      <span className="max-w-24 truncate">{row.company}</span>
                      <span className="tabular-nums">{Math.round(row.overall_coverage)}%</span>
                    </Badge>
                  ))}
                  {(sourcesOverview?.items ?? []).length === 0 && (
                    <span className="text-xs text-muted-foreground">No profiles audited yet</span>
                  )}
                </div>
              </CardContent>
            </Card>
            <Card className="flex flex-col justify-center p-5">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Action Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 text-sm">
                {(health?.suggestions ?? scHealth?.suggestions ?? []).slice(0, 3).map((s, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                    <span className="text-muted-foreground">{s}</span>
                  </div>
                ))}
                <div className="flex items-center gap-2 pt-1">
                  <Truck className="h-4 w-4 text-chart-3" />
                  <span className="text-xs text-muted-foreground">3 shipments in transit, 1 delayed</span>
                </div>
                <div className="flex items-center gap-2">
                  <Boxes className="h-4 w-4 text-chart-4" />
                  <span className="text-xs text-muted-foreground">2 inventory anomalies require action</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Charts */}
          <div id="charts" className="scroll-mt-28 grid gap-4 lg:grid-cols-2">
            <ChartCard
              id="revenue-trend"
              title="Revenue Trend"
              description="12-month revenue trajectory (modeled)"
              csvData={revenueSeries}
              csvColumns={[{ key: "label", label: "Month" }, { key: "value", label: "Revenue" }]}
            >
              <LineAreaChart data={revenueSeries} xKey="label" type="area" series={[{ key: "value", name: "Revenue", area: true }]} formatter={(v) => formatCurrency(v, { compact: true })} />
            </ChartCard>
            <ChartCard
              id="profit-trend"
              title="Profit Trend"
              description="12-month profitability (modeled)"
              csvData={profitSeries}
            >
              <LineAreaChart data={profitSeries} xKey="label" type="line" series={[{ key: "value", name: "Profit" }]} formatter={(v) => formatCurrency(v, { compact: true })} />
            </ChartCard>
          </div>

          {/* Trade-route risk radar (live news) */}
          <div id="risk-radar" className="scroll-mt-28">
            <RiskRadar
              scenarios={routeRisk?.scenarios ?? []}
              mode={routeRisk?.mode}
              loading={radarLoading}
              limit={3}
              title="Trade Route Risk Radar"
              description="Live chokepoint disruptions from today's headlines — simulate in Route Diversion"
            />
          </div>

          <div id="simulations" className="scroll-mt-28 grid gap-4 lg:grid-cols-3">
            <ChartCard id="cashflow" title="Cash Flow" description="Operating cash flow by month" className="lg:col-span-1" csvData={cashflowSeries}>
              <BarChartComponent data={cashflowSeries} xKey="label" series={[{ key: "value", name: "Cash flow" }]} formatter={(v) => formatCurrency(v, { compact: true })} />
            </ChartCard>

            {/* Recent simulations */}
            <Card className="lg:col-span-1">
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-sm">Recent Simulations</CardTitle>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/timeline">View all <ArrowRight /></Link>
                </Button>
              </CardHeader>
              <CardContent className="space-y-2">
                {timelineLoading ? (
                  <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-14 animate-pulse rounded-md bg-muted" />)}</div>
                ) : (
                  (timeline ?? []).slice(0, 4).map((t, i) => (
                    <motion.div
                      key={t.simulation_id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="flex items-center justify-between rounded-md border px-3 py-2.5 transition-colors hover:bg-accent/50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{DECISION_TYPE_MAP[t.decision_type]?.label ?? t.decision_type}</p>
                        <p className="text-xs text-muted-foreground"><RelativeTime value={t.created_at} /> · confidence {t.confidence_score}%</p>
                      </div>
                      <div className="text-right text-xs">
                        <p className="font-semibold tabular-nums text-success">+{formatDelta(t.predicted_revenue - (twin?.revenue ?? 0), { percent: false, suffix: "" })}</p>
                        <p className="tabular-nums text-muted-foreground">{formatCurrency(t.predicted_revenue, { compact: true })}</p>
                      </div>
                    </motion.div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Notifications */}
            <Card className="lg:col-span-1">
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-sm">Notifications</CardTitle>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/alerts">Alerts center <ArrowRight /></Link>
                </Button>
              </CardHeader>
              <CardContent className="space-y-2">
                {(alerts ?? []).slice(0, 4).map((n, i) => (
                  <motion.div
                    key={n.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-start gap-2.5 rounded-md border px-3 py-2.5"
                  >
                    <SeverityBadge severity={n.severity} className="mt-0.5 shrink-0 !px-1.5 !text-[10px]" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{n.title}</p>
                      <p className="line-clamp-1 text-xs text-muted-foreground">{n.description}</p>
                      <p className="mt-0.5 text-[10px] text-muted-foreground/70"><RelativeTime value={n.created_at} /></p>
                    </div>
                  </motion.div>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* AI Recommendations */}
          <div id="recommendations" className="scroll-mt-28 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-chart-3" />
                <h2 className="font-semibold">Today&apos;s AI Recommendations</h2>
              </div>
              <Button asChild variant="ghost" size="sm">
                <Link href="/insights">All insights <ArrowRight /></Link>
              </Button>
            </div>
            {strategiesLoading ? (
              <SkeletonGrid count={3} />
            ) : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {(strategies?.strategies ?? []).slice(0, 3).map((s, i) => (
                  <RecommendationCard key={s.title} strategy={s} index={i} />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Executive briefing dialog */}
      <Dialog open={briefingOpen} onOpenChange={setBriefingOpen}>
        <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" /> Executive Briefing{briefing ? ` — ${briefing.company}` : ""}
            </DialogTitle>
            <DialogDescription>Generated by the agentic pipeline · {briefing?.mode === "llm" ? "LLM-synthesized" : "news + rules"}</DialogDescription>
          </DialogHeader>
          {briefingLoading ? (
            <div className="space-y-3 py-6">
              {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />)}
            </div>
          ) : briefing ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Health score</p>
                  <p className="text-2xl font-bold tabular-nums">{briefing.health_score}/100</p>
                </div>
                <p className="max-w-sm text-sm text-muted-foreground">{briefing.summary.split("\n")[0]}</p>
              </div>
              {briefing.sections.map((s, i) => (
                <AnimatePresence key={s.title}>
                  <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }} className="rounded-lg border p-4">
                    <p className="mb-1 flex items-center gap-2 text-sm font-semibold">
                      <Sparkles className="h-3.5 w-3.5 text-chart-3" /> {s.title}
                      <span className="text-[10px] font-normal text-muted-foreground">· {s.source}</span>
                    </p>
                    <p className="whitespace-pre-line text-sm text-muted-foreground">{s.body}</p>
                  </motion.div>
                </AnimatePresence>
              ))}
              <div className="rounded-lg border border-border bg-muted/40 p-4">
                <p className="mb-2 text-sm font-semibold">Top recommendations</p>
                <ul className="space-y-1.5">
                  {briefing.top_recommendations.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" /> {r}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
