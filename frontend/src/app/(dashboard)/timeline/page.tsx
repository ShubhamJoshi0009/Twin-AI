"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { History, Play, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { SearchBar } from "@/components/shared/search-bar";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/shared/state-views";
import { useTimeline, useTwins } from "@/hooks/use-api";
import * as business from "@/lib/api/business";
import { errorMessage } from "@/lib/api/client";
import { DECISION_TYPE_MAP } from "@/lib/constants";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import { isDemoTwinId, MOCK_SIMULATION } from "@/lib/mock/mock-data";
import type { TimelineEntry } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

export default function TimelinePage() {
  const { data: twins } = useTwins();
  const twinId = twins?.[0]?.id ?? null;
  const { data: timeline, isLoading, refetch } = useTimeline(twinId);
  const [query, setQuery] = useState("");
  const [replayId, setReplayId] = useState<string | null>(null);
  const [deleted, setDeleted] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return (timeline ?? []).filter((t) => !deleted.has(t.simulation_id)).filter((t) => {
      const label = DECISION_TYPE_MAP[t.decision_type]?.label ?? t.decision_type;
      return label.toLowerCase().includes(q) || t.simulation_id.toLowerCase().includes(q) || t.created_at.includes(q);
    });
  }, [timeline, query, deleted]);

  const handleDelete = (id: string) => {
    setDeleted((prev) => new Set(prev).add(id));
    toast.success("Simulation removed from timeline");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Business Timeline"
        description="History of every decision simulation — replay or remove entries"
        actions={<SearchBar value={query} onChange={setQuery} placeholder="Search by decision…" className="w-full max-w-sm" />}
      />

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />)}</div>
      ) : filtered.length === 0 ? (
        <Card>
          <EmptyState
            title={deleted.size > 0 ? "Timeline cleared" : "No simulations yet"}
            description={deleted.size > 0 ? "Run new simulations in the Scenario Simulator to rebuild the timeline." : "Every simulation you run will appear here for replay and review."}
            action={<Button onClick={() => refetch()}>Refresh</Button>}
          />
        </Card>
      ) : (
        <div className="relative space-y-0 pl-6 before:absolute before:bottom-2 before:left-[7px] before:top-2 before:w-px before:bg-border">
          {filtered.map((t, i) => (
            <motion.div
              key={t.simulation_id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="relative pb-5"
            >
              <span className="absolute -left-6 top-1.5 flex h-4 w-4 items-center justify-center rounded-full border-2 border-primary bg-card">
                <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              </span>
              <Card className="transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md">
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <History className="h-4 w-4" />
                    </span>
                    <div>
                      <CardTitle className="text-sm capitalize">
                        {DECISION_TYPE_MAP[t.decision_type]?.label ?? t.decision_type.replaceAll("_", " ")}
                      </CardTitle>
                      <CardDescription className="text-xs">{formatDateTime(t.created_at)} · {t.simulation_id.slice(0, 8)}</CardDescription>
                    </div>
                  </div>
                  <Badge variant="secondary">Confidence {t.confidence_score}%</Badge>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat label="Revenue" value={formatCurrency(t.predicted_revenue, { compact: true })} />
                    <Stat label="Profit" value={formatCurrency(t.predicted_profit, { compact: true })} />
                    <Stat label="Confidence" value={`${t.confidence_score}%`} />
                    <Stat
                      label="Recommendation"
                      value={typeof t.recommendation?.recommendation === "string" ? t.recommendation.recommendation : "—"}
                      truncate
                    />
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => setReplayId(t.simulation_id)}>
                      <Play /> Replay
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive">
                          <Trash2 /> Delete
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Remove this simulation?</AlertDialogTitle>
                          <AlertDialogDescription>It will be removed from the timeline view. This cannot be undone.</AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDelete(t.simulation_id)}>Delete</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {/* Replay dialog */}
      <Dialog open={!!replayId} onOpenChange={(o) => !o && setReplayId(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Replaying Simulation</DialogTitle>
            <DialogDescription>Fetching the full simulation record from the timeline…</DialogDescription>
          </DialogHeader>
          {replayId && <ReplayContent twinId={twinId} simId={replayId} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Stat({ label, value, truncate }: { label: string; value: string; truncate?: boolean }) {
  return (
    <div className="rounded-md bg-muted/60 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`mt-0.5 text-sm font-semibold tabular-nums ${truncate ? "line-clamp-2" : ""}`}>{value}</p>
    </div>
  );
}

function ReplayContent({ twinId, simId }: { twinId: string | null; simId: string }) {
  const { data: sim, isLoading, error } = useQuery({
    queryKey: ["replay", twinId, simId],
    queryFn: () => (isDemoTwinId(twinId) ? Promise.resolve(MOCK_SIMULATION) : business.getSimulation(twinId ?? "demo-twin-001", simId)),
    retry: 1,
  });

  if (isLoading) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;
  if (error || !sim) return <p className="text-sm text-destructive">{errorMessage(error ?? new Error("not found"))}</p>;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(sim.predictions).slice(0, 6).map(([k, p]) => (
          <div key={k} className="rounded-md border p-3">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{k.replaceAll("_", " ")}</p>
            <p className="mt-0.5 text-sm font-bold tabular-nums">{formatCurrency(p.predicted, { compact: true })}</p>
            <p className={`text-xs tabular-nums ${p.change_percent >= 0 ? "text-success" : "text-destructive"}`}>
              {p.change_percent >= 0 ? "+" : ""}{p.change_percent.toFixed(1)}%
            </p>
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
        <p className="text-sm font-semibold">{sim.recommendation.recommendation}</p>
        <p className="mt-1 text-xs text-muted-foreground">{sim.recommendation.reasoning}</p>
      </div>
    </div>
  );
}
