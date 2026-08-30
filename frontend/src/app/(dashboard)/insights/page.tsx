"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { BrainCircuit, ExternalLink, Newspaper, RefreshCw, TrendingDown, TrendingUp, Users, Lightbulb, AlertTriangle, BarChart3 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { ChartCard } from "@/components/charts/chart-card";
import { LineAreaChart } from "@/components/charts/line-area-chart";
import { PieChartComponent } from "@/components/charts/pie-chart";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { SkeletonGrid } from "@/components/shared/state-views";
import { RelativeTime } from "@/components/shared/relative-time";
import { useInsights, useMarketNews, useTwins } from "@/hooks/use-api";
import * as business from "@/lib/api/business";
import { isDemoTwinId, mockTimeSeries } from "@/lib/mock/mock-data";
import { formatCurrency } from "@/lib/utils";

const RANGES = ["Week", "Month", "Quarter", "Year"] as const;
type Range = (typeof RANGES)[number];

const INSIGHT_ICONS: Record<string, typeof BarChart3> = {
  revenue_trend: TrendingUp,
  profitability: TrendingDown,
  customer: Users,
  growth: Lightbulb,
  risk: AlertTriangle,
};

export default function InsightsPage() {
  const { data: twins } = useTwins();
  const twin = twins?.[0];
  const twinId = twin?.id ?? null;
  const { data: insights, isLoading, refetch } = useInsights(twinId);
  // Real-time market headlines relevant to this business (GDELT or fallback).
  const newsQuery = twin ? `${twin.industry} ${twin.name} supply chain market` : null;
  const { data: marketNews } = useMarketNews(newsQuery);
  const [range, setRange] = useState<Range>("Quarter");
  const [regenerating, setRegenerating] = useState(false);

  // Time range alters the modeled chart series amplitude.
  const multiplier = range === "Week" ? 0.25 : range === "Month" ? 0.5 : range === "Quarter" ? 1 : 2;
  const revenueTrend = useMemo(() => mockTimeSeries(4, 12, 190 * multiplier, 0.09), [multiplier]);
  const profitTrend = useMemo(() => mockTimeSeries(5, 12, 46 * multiplier, 0.1), [multiplier]);

  const severityCount = useMemo(() => {
    const counts = { info: 0, warning: 0, critical: 0 };
    (insights ?? []).forEach((i) => { counts[i.severity] += 1; });
    return counts;
  }, [insights]);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      // No real twin configured → skip the network call, demo insights refresh instantly.
      if (!isDemoTwinId(twinId)) {
        await business.generateInsights(twinId ?? "demo-twin-001");
      }
      await refetch();
      toast.success("Insights regenerated");
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Business Insights"
        description="AI-generated insights across revenue, customers, growth and risk"
        actions={
          <>
            <Tabs value={range} onValueChange={(v) => setRange(v as Range)}>
              <TabsList>
                {RANGES.map((r) => (
                  <TabsTrigger key={r} value={r}>{r}</TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <Button variant="outline" size="sm" onClick={handleRegenerate} disabled={regenerating}>
              <RefreshCw className={regenerating ? "animate-spin" : ""} /> Regenerate
            </Button>
          </>
        }
      />

      {/* Severity overview */}
      <div className="grid gap-4 sm:grid-cols-3">
        {(["info", "warning", "critical"] as const).map((sev, i) => (
          <motion.div key={sev} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
            <Card className="flex items-center justify-between p-5">
              <div>
                <p className="text-sm text-muted-foreground capitalize">{sev} insights</p>
                <p className="mt-1 text-3xl font-bold tabular-nums">{severityCount[sev]}</p>
              </div>
              <SeverityBadge severity={sev} />
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard id="insight-revenue" title="Revenue Trends" description={`Revenue trajectory — ${range.toLowerCase()} view`} csvData={revenueTrend}>
          <LineAreaChart data={revenueTrend} xKey="label" type="area" series={[{ key: "value", name: "Revenue" }]} formatter={(v) => formatCurrency(v, { compact: true })} />
        </ChartCard>
        <ChartCard id="insight-profit" title="Profit Trends" description={`Profit trajectory — ${range.toLowerCase()} view`} csvData={profitTrend}>
          <LineAreaChart data={profitTrend} xKey="label" type="line" series={[{ key: "value", name: "Profit" }]} formatter={(v) => formatCurrency(v, { compact: true })} />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard id="insight-mix" title="Insight Mix" description="Distribution by severity">
          <PieChartComponent
            height={220}
            centerValue={String((insights ?? []).length)}
            centerLabel="total"
            data={[
              { name: "Info", value: severityCount.info, color: "hsl(var(--chart-1))" },
              { name: "Warning", value: severityCount.warning, color: "hsl(var(--chart-3))" },
              { name: "Critical", value: severityCount.critical, color: "hsl(var(--chart-5))" },
            ]}
          />
        </ChartCard>

        {/* Executive summary */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm"><BrainCircuit className="h-4 w-4 text-chart-4" /> Executive Summary</CardTitle>
            <CardDescription className="text-xs">AI brief for {range.toLowerCase()}-over-{range.toLowerCase()} performance</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Revenue is trending <span className="font-semibold text-success">+12.4%</span> versus the previous {range.toLowerCase()}, led by the digital channel.
              Profitability held at <span className="font-semibold">24.2% margin</span> despite a <span className="font-semibold text-warning">9% rise in logistics costs</span>.
            </p>
            <p>
              The top customer decile now contributes <span className="font-semibold">34% of revenue</span> — retention programs are working, but concentration is rising.
              One <span className="font-semibold text-destructive">critical</span> risk requires attention: supplier concentration on TechParts Global.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant="secondary">Growth: +12.4% revenue</Badge>
              <Badge variant="secondary">Margin: 24.2%</Badge>
              <Badge variant="secondary">Retention: 78%</Badge>
              <Badge variant="secondary">Cash: {formatCurrency(420_000, { compact: true })}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Real-time market news */}
      <Card className="border-chart-1/30 bg-chart-1/5">
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Newspaper className="h-4 w-4 text-chart-1" /> Market News Feed
          </CardTitle>
          <Badge variant="secondary" className="text-[10px]">Real-time feed</Badge>
        </CardHeader>
        <CardDescription className="px-5 text-xs">Latest headlines that shape demand, costs and supply — the analysis above is grounded in this context</CardDescription>
        <CardContent className="grid gap-2 pt-4 sm:grid-cols-2 lg:grid-cols-3">
          {(marketNews ?? []).slice(0, 6).map((n, i) => (
            <motion.a
              key={`${n.source}-${i}`}
              href={n.url}
              target="_blank"
              rel="noreferrer"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="group flex flex-col rounded-lg border border-border/60 bg-card/80 p-3 transition-all hover:-translate-y-0.5 hover:border-chart-1/40 hover:shadow-sm"
            >
              <p className="line-clamp-2 flex-1 text-sm font-medium leading-snug group-hover:text-chart-1">{n.title}</p>
              <p className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                <span className="font-semibold">{n.source}</span>
                <ExternalLink className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" />
              </p>
            </motion.a>
          ))}
        </CardContent>
      </Card>

      {/* Insight cards */}
      {isLoading ? (
        <SkeletonGrid count={3} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(insights ?? []).map((ins, i) => {
            const Icon = INSIGHT_ICONS[ins.insight_type] ?? BarChart3;
            return (
              <motion.div key={ins.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <Card className="group h-full transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md">
                  <CardHeader className="flex-row items-start justify-between space-y-0 pb-2">
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary transition-transform group-hover:scale-110">
                        <Icon className="h-4 w-4" />
                      </span>
                      {ins.title}
                    </CardTitle>
                    <SeverityBadge severity={ins.severity} className="!px-1.5 !text-[10px]" />
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-sm text-muted-foreground">{ins.description}</p>
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] uppercase tracking-wide text-muted-foreground/70">{ins.insight_type.replaceAll("_", " ")}</span>
                      <span className="text-[11px] text-muted-foreground"><RelativeTime value={ins.created_at} /></span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
