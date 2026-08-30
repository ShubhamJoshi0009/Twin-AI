"use client";

import { motion } from "framer-motion";
import { Anchor, ArrowRight, Newspaper, Radar, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SkeletonGrid, EmptyState } from "@/components/shared/state-views";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { cn } from "@/lib/utils";
import type { RouteRiskScenario } from "@/lib/types";

const EVENT_ICON: Record<string, string> = {
  war_conflict: "⚔️",
  piracy: "🏴‍☠️",
  natural_disaster: "🌪️",
  sanctions: "🚫",
  congestion: "🚢",
  grounding: "🧊",
};

function riskColor(score: number) {
  if (score >= 70) return { bar: "bg-red-500", text: "text-red-500" };
  if (score >= 50) return { bar: "bg-orange-500", text: "text-orange-500" };
  if (score >= 30) return { bar: "bg-amber-500", text: "text-amber-500" };
  return { bar: "bg-emerald-500", text: "text-emerald-500" };
}

export function RiskScenarioRow({
  scenario,
  onApply,
  index = 0,
  compact = false,
}: {
  scenario: RouteRiskScenario;
  onApply?: (s: RouteRiskScenario) => void;
  index?: number;
  compact?: boolean;
}) {
  const color = riskColor(scenario.risk_score);
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className={cn(
        "group relative overflow-hidden rounded-lg border border-border/60 bg-card/60 p-3 transition-all hover:border-amber-500/40 hover:bg-card",
        compact && "p-2.5"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          <span className="text-base leading-none">{EVENT_ICON[scenario.event_type] ?? "🚨"}</span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
              {scenario.chokepoint_name}
              <Badge variant="secondary" className="!px-1.5 !text-[9px] normal-case">
                {scenario.region}
              </Badge>
            </div>
            <a
              href={scenario.url || "#"}
              target="_blank"
              rel="noreferrer"
              className="mt-0.5 line-clamp-2 block text-[11px] text-muted-foreground transition-colors group-hover:text-foreground"
              title={scenario.headline}
            >
              {scenario.headline}
            </a>
            <p className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground/70">
              <Newspaper className="h-2.5 w-2.5" /> {scenario.source} · {scenario.event_label}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <span className={cn("font-mono text-sm font-bold tabular-nums", color.text)}>{scenario.risk_score}</span>
          <SeverityBadge severity={scenario.severity} className="!px-1.5 !text-[9px]" />
        </div>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full transition-all duration-700", color.bar)} style={{ width: `${scenario.risk_score}%` }} />
      </div>
      {onApply && (
        <Button
          size="sm"
          variant="outline"
          className="mt-2 h-7 w-full gap-1.5 border-amber-500/30 text-[11px] text-amber-600 transition-colors hover:bg-amber-500/10 hover:text-amber-500 dark:text-amber-400"
          onClick={() => onApply(scenario)}
        >
          <Zap className="h-3 w-3" /> Apply & simulate
        </Button>
      )}
    </motion.div>
  );
}

export function RiskRadar({
  scenarios,
  mode,
  loading,
  error,
  onApply,
  limit = 6,
  title = "Live Risk Radar",
  description = "Trade-route scenarios discovered from today's headlines — click to simulate on the world map",
  onRetry,
}: {
  scenarios: RouteRiskScenario[];
  mode?: string;
  loading?: boolean;
  error?: string | null;
  onApply?: (s: RouteRiskScenario) => void;
  limit?: number;
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <Card className="border-amber-500/20">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <div>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Radar className="h-4 w-4 text-amber-500" /> {title}
          </CardTitle>
          <CardDescription className="text-xs">{description}</CardDescription>
        </div>
        <Badge variant={mode === "live" ? "warning" : "secondary"} className="shrink-0 font-mono text-[9px]">
          {mode === "live" ? "live news" : "curated feed"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-2">
        {loading ? (
          <SkeletonGrid count={3} className="!grid-cols-1" />
        ) : error ? (
          <div className="space-y-2">
            <EmptyState
              title="Risk radar unavailable"
              description={error}
              action={
                onRetry ? (
                  <Button variant="outline" size="sm" onClick={onRetry}>
                    Retry
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : scenarios.length === 0 ? (
          <EmptyState
            title="No route scenarios detected"
            description="No chokepoint disruptions were found in the latest headlines."
          />
        ) : (
          scenarios.slice(0, limit).map((s, i) => (
            <RiskScenarioRow key={s.scenario_id} scenario={s} onApply={onApply} index={i} />
          ))
        )}
      </CardContent>
    </Card>
  );
}

export function RiskRadarStrip({
  scenarios,
  mode,
  loading,
  onApply,
}: {
  scenarios: RouteRiskScenario[];
  mode?: string;
  loading?: boolean;
  onApply?: (s: RouteRiskScenario) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Anchor className="h-4 w-4 text-amber-500" />
        <h2 className="font-semibold">Trade Route Alerts</h2>
        <Badge variant={mode === "live" ? "warning" : "secondary"} className="font-mono text-[9px]">
          {mode === "live" ? "live news" : "curated feed"}
        </Badge>
        {onApply && <ArrowRight className="ml-auto h-3.5 w-3.5 text-muted-foreground" />}
      </div>
      {loading ? (
        <SkeletonGrid count={3} className="!grid-cols-1 md:!grid-cols-3" />
      ) : scenarios.length === 0 ? (
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">
            No trade-route disruptions in today&apos;s headlines.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-3">
          {scenarios.map((s, i) => (
            <RiskScenarioRow key={s.scenario_id} scenario={s} onApply={onApply} index={i} compact />
          ))}
        </div>
      )}
    </div>
  );
}
