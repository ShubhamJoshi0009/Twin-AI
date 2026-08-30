"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowDownRight,
  ArrowUpRight,
  CandlestickChart,
  Gauge,
  Globe2,
  Newspaper,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Waves,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { RiskRadarStrip } from "@/components/route-risk/risk-radar";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, SkeletonGrid, ErrorState } from "@/components/shared/state-views";
import { useMarketWatch, useRouteRiskScenarios } from "@/hooks/use-api";
import { useMounted } from "@/hooks/use-mounted";
import { cn } from "@/lib/utils";
import type { WatchItem } from "@/lib/types";

const CATEGORY_META: Record<string, { label: string; icon: typeof Gauge; cls: string }> = {
  commodity: { label: "Commodity", icon: Gauge, cls: "text-amber-500 bg-amber-500/10" },
  freight: { label: "Freight", icon: Waves, cls: "text-sky-500 bg-sky-500/10" },
  geopolitical: { label: "Geopolitical", icon: Globe2, cls: "text-rose-500 bg-rose-500/10" },
  index: { label: "Index", icon: CandlestickChart, cls: "text-emerald-500 bg-emerald-500/10" },
};

const SENTIMENT_CLS: Record<string, string> = {
  positive: "text-success border-success/30 bg-success/10",
  negative: "text-destructive border-destructive/30 bg-destructive/10",
  neutral: "text-muted-foreground border-border bg-muted/40",
  mixed: "text-warning border-warning/30 bg-warning/10",
};

export default function MarketWatchPage() {
  const mounted = useMounted();
  const { data, isLoading, error, refetch, isFetching } = useMarketWatch();
  const { data: routeRisk, isLoading: radarLoading } = useRouteRiskScenarios(3);
  const [filter, setFilter] = useState<string>("all");

  const items = useMemo(() => (filter === "all" ? (data?.items ?? []) : (data?.items ?? []).filter((i) => i.category === filter)), [data, filter]);

  if (!mounted) return <SkeletonGrid count={4} />;
  if (error) return <ErrorState message={error.userMessage ?? error.message} onRetry={() => refetch()} />;

  const categories = ["all", ...new Set((data?.items ?? []).map((i) => i.category))];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Market Watch"
        description="Commodities, freight and geopolitical drivers tracked against live headlines — with estimated impact on your business"
        actions={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} /> Refresh
          </Button>
        }
      />

      {/* Trade Route Alerts — news-driven chokepoint scenarios */}
      <RiskRadarStrip
        scenarios={routeRisk?.scenarios ?? []}
        mode={routeRisk?.mode}
        loading={radarLoading}
      />

      {/* Market context banner */}
      {data?.market_context && (
        <div className="flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
          <Newspaper className="h-4 w-4 shrink-0 text-primary" />
          <p className="text-sm">{data.market_context}</p>
          <Badge variant="secondary" className="ml-auto shrink-0 font-mono text-[10px]">
            live feed
          </Badge>
        </div>
      )}

      {/* Filter chips */}
      <div className="flex flex-wrap gap-1.5">
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setFilter(c)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs capitalize transition-colors",
              filter === c ? "border-primary/60 bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/40"
            )}
          >
            {c}
          </button>
        ))}
      </div>

      {isLoading ? (
        <SkeletonGrid count={4} />
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            title="No market data available"
            description="Connect to the backend to load the live market watch — commodities, freight and geopolitical drivers."
            action={<Button variant="outline" size="sm" onClick={() => refetch()}>Retry</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item: WatchItem, i) => {
            const cat = CATEGORY_META[item.category] ?? CATEGORY_META.index;
            const CatIcon = cat.icon;
            return (
              <motion.div key={item.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <Card className="h-full transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md">
                  <CardHeader className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className={cn("flex h-8 w-8 items-center justify-center rounded-lg", cat.cls)}>
                          <CatIcon className="h-4 w-4" />
                        </span>
                        <div>
                          <CardTitle className="text-sm">{item.name}</CardTitle>
                          <CardDescription className="text-[11px] capitalize">{item.category}</CardDescription>
                        </div>
                      </div>
                      <Badge className={cn("text-[10px]", SENTIMENT_CLS[item.sentiment] ?? SENTIMENT_CLS.neutral)}>
                        {item.sentiment}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {/* Impact meter */}
                    <div>
                      <div className="mb-1 flex items-center justify-between text-[11px]">
                        <span className="text-muted-foreground">Impact on business</span>
                        <span className="flex items-center gap-1 font-semibold tabular-nums">
                          {item.direction === "negative" ? <ArrowDownRight className="h-3 w-3 text-destructive" /> : item.direction === "positive" ? <ArrowUpRight className="h-3 w-3 text-success" /> : <span className="h-3 w-3" />}
                          {item.impact_score}/100
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${item.impact_score}%` }}
                          transition={{ duration: 0.8, delay: 0.1 + i * 0.05 }}
                          className={cn(
                            "h-full rounded-full",
                            item.direction === "negative" ? "bg-destructive" : item.direction === "positive" ? "bg-success" : "bg-warning"
                          )}
                        />
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                        {item.trend === "up" ? <TrendingUp className="h-3 w-3 text-success" /> : item.trend === "down" ? <TrendingDown className="h-3 w-3 text-destructive" /> : <Waves className="h-3 w-3 text-warning" />}
                        <span className="capitalize">trend: {item.trend}</span>
                      </div>
                    </div>

                    <p className="text-xs text-muted-foreground">{item.rationale}</p>

                    {item.news.length > 0 && (
                      <div className="space-y-1.5 border-t pt-2.5">
                        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Top headlines</p>
                        {item.news.slice(0, 2).map((n, ni) => (
                          <a key={ni} href={n.url || "#"} target="_blank" rel="noreferrer" className="group block">
                            <p className="line-clamp-2 text-xs transition-colors group-hover:text-primary">{n.title}</p>
                            <p className="text-[10px] text-muted-foreground/70">{n.source}</p>
                          </a>
                        ))}
                      </div>
                    )}
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
