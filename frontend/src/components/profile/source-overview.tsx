"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, CheckCircle2, Layers, ListChecks } from "lucide-react";
import { useSourcesOverview } from "@/hooks/use-api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SkeletonGrid } from "@/components/shared/state-views";
import { cn } from "@/lib/utils";
import type { SourceChecklistOverviewItem } from "@/lib/types";

interface SourceOverviewProps {
  /** twin_id of the currently selected profile (highlighted row). */
  selectedTwinId?: string | null;
  /** Called when the user clicks a profile row. */
  onSelect?: (twinId: string) => void;
}

function coverageColor(score: number) {
  if (score >= 70) return "hsl(var(--success))";
  if (score >= 40) return "hsl(var(--chart-3))";
  return "hsl(var(--destructive))";
}

function OverviewRow({
  item,
  selected,
  onSelect,
  index,
}: {
  item: SourceChecklistOverviewItem;
  selected: boolean;
  onSelect?: (twinId: string) => void;
  index: number;
}) {
  const color = coverageColor(item.overall_coverage);
  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.05 }}
      onClick={() => onSelect?.(item.twin_id)}
      aria-pressed={selected}
      className={cn(
        "group flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all",
        selected
          ? "border-primary/40 bg-primary/5 shadow-sm"
          : "border-border hover:border-primary/25 hover:bg-accent/40"
      )}
    >
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-xs font-bold"
        style={{ backgroundColor: `${color}1a`, color }}
      >
        {Math.round(item.overall_coverage)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-sm font-semibold">{item.company}</span>
          {item.regressed && (
            <Badge variant="destructive" className="gap-1 !px-1.5 !text-[10px]">
              <AlertTriangle className="h-3 w-3" /> regressed
            </Badge>
          )}
        </span>
        <span className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span className="capitalize">{item.industry}</span>
          <span>·</span>
          <span>{item.completed_count}/{item.total_sections} complete</span>
          <span>·</span>
          <span>{item.verified_count} verified</span>
          {item.missing_count > 0 && <span>· {item.missing_count} missing</span>}
        </span>
      </span>
      <span className="flex w-24 shrink-0 items-center gap-2">
        <span className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
          <span
            className="block h-full rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.min(100, Math.max(0, item.overall_coverage))}%`, backgroundColor: color }}
          />
        </span>
        <ArrowRight
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-all",
            selected ? "translate-x-0 text-primary" : "-translate-x-1 opacity-0 group-hover:translate-x-0 group-hover:opacity-100"
          )}
        />
      </span>
    </motion.button>
  );
}

/**
 * Cross-profile source-coverage overview. Lists one row per business profile
 * with coverage, completion, verified/missing counts, and a regression flag —
 * clicking a row selects that profile (drives the digital-twin graph + checklist).
 */
export function SourceOverview({ selectedTwinId, onSelect }: SourceOverviewProps) {
  const { data, isLoading } = useSourcesOverview();

  const { items, avgCoverage, totalProfiles } = useMemo(() => {
    const rows = data?.items ?? [];
    const avg = rows.length ? rows.reduce((s, r) => s + r.overall_coverage, 0) / rows.length : 0;
    return { items: rows, avgCoverage: avg, totalProfiles: rows.length };
  }, [data]);

  if (isLoading && items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Profile Coverage Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <SkeletonGrid count={2} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Layers className="h-4 w-4 text-chart-3" /> Profile Coverage Overview
          </CardTitle>
          <CardDescription className="text-xs">
            {totalProfiles
              ? `${totalProfiles} business profile${totalProfiles === 1 ? "" : "s"} · average ${Math.round(avgCoverage)}% coverage — click a profile to select it`
              : "Source coverage across all business profiles"}
          </CardDescription>
        </div>
        {items.length > 0 && (
          <Badge variant="secondary" className="gap-1 text-[10px]">
            <ListChecks className="h-3 w-3" /> avg {Math.round(avgCoverage)}%
          </Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        {items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <CheckCircle2 className="h-7 w-7 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              No business profiles yet — create one to see its source coverage here.
            </p>
            <Button asChild variant="outline" size="sm">
              <a href="/digital-twin">View digital twin</a>
            </Button>
          </div>
        ) : (
          items.map((item, i) => (
            <OverviewRow
              key={item.twin_id}
              item={item}
              index={i}
              selected={selectedTwinId === item.twin_id}
              onSelect={onSelect}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
