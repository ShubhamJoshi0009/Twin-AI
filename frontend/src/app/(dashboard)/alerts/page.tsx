"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Bell, CheckCheck, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { SearchBar } from "@/components/shared/search-bar";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { KPICard } from "@/components/kpi/kpi-card";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/shared/state-views";
import { RelativeTime } from "@/components/shared/relative-time";
import { useAlerts } from "@/hooks/use-api";
import type { Alert, Severity } from "@/lib/types";

type Filter = "all" | Severity;
type Sort = "newest" | "oldest" | "severity";

export default function AlertsCenterPage() {
  const { data: alerts, isLoading, refetch } = useAlerts();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("newest");
  const [resolved, setResolved] = useState<Set<string>>(new Set());

  const counts = useMemo(() => ({
    critical: (alerts ?? []).filter((a) => a.severity === "critical").length,
    high: (alerts ?? []).filter((a) => a.severity === "high").length,
    medium: (alerts ?? []).filter((a) => a.severity === "medium").length,
    low: (alerts ?? []).filter((a) => a.severity === "low").length,
  }), [alerts]);

  const visible = useMemo(() => {
    const q = query.toLowerCase();
    let list = (alerts ?? []).filter((a) => !resolved.has(a.id));
    if (filter !== "all") list = list.filter((a) => a.severity === filter);
    if (q) list = list.filter((a) => a.title.toLowerCase().includes(q) || a.description.toLowerCase().includes(q) || a.alert_type.toLowerCase().includes(q));
    list = [...list].sort((a, b) => {
      if (sort === "newest") return +new Date(b.created_at) - +new Date(a.created_at);
      if (sort === "oldest") return +new Date(a.created_at) - +new Date(b.created_at);
      const order = { critical: 4, high: 3, medium: 2, low: 1 } as const;
      return order[b.severity as keyof typeof order] - order[a.severity as keyof typeof order];
    });
    return list;
  }, [alerts, query, filter, sort, resolved]);

  const markResolved = (id: string, title: string) => {
    setResolved((prev) => new Set(prev).add(id));
    toast.success(`“${title}” resolved`);
  };

  const markAll = () => {
    setResolved((prev) => new Set([...prev, ...visible.map((a) => a.id)]));
    toast.success(`${visible.length} alerts resolved`);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alerts Center"
        description="Prioritized operational alerts with suggested actions"
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => refetch()}><RefreshCw /> Refresh</Button>
            <Button variant="outline" size="sm" onClick={markAll} disabled={visible.length === 0}><CheckCheck /> Resolve all</Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KPICard label="Critical" value={String(counts.critical)} icon={Bell} delta={null} />
        <KPICard label="High" value={String(counts.high)} icon={Bell} delta={null} />
        <KPICard label="Medium" value={String(counts.medium)} icon={Bell} delta={null} />
        <KPICard label="Low" value={String(counts.low)} icon={Bell} delta={null} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <SearchBar value={query} onChange={setQuery} placeholder="Search alerts…" className="w-full max-w-sm" />
        <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
          <TabsList className="flex-wrap">
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="critical">Critical</TabsTrigger>
            <TabsTrigger value="high">High</TabsTrigger>
            <TabsTrigger value="medium">Medium</TabsTrigger>
            <TabsTrigger value="low">Low</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant="secondary">Sort</Badge>
          <Tabs value={sort} onValueChange={(v) => setSort(v as Sort)}>
            <TabsList>
              <TabsTrigger value="severity">Severity</TabsTrigger>
              <TabsTrigger value="newest">Newest</TabsTrigger>
              <TabsTrigger value="oldest">Oldest</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />)}</div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            title={resolved.size > 0 ? "All alerts resolved 🎉" : "No alerts match your filters"}
            description={resolved.size > 0 ? "The operations queue is clear. New alerts will appear here automatically." : "Try adjusting the search or severity filter."}
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {visible.map((alert, i) => (
            <AlertRow key={alert.id} alert={alert} index={i} onResolve={() => markResolved(alert.id, alert.title)} />
          ))}
        </div>
      )}
    </div>
  );
}

function AlertRow({ alert, index, onResolve }: { alert: Alert; index: number; onResolve: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      whileHover={{ y: -2 }}
      className="rounded-lg border bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-start gap-3">
        <SeverityBadge severity={alert.severity} className="mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{alert.title}</h3>
            <Badge variant="secondary" className="text-[10px] capitalize">{alert.alert_type}</Badge>
            <span className="text-xs text-muted-foreground"><RelativeTime value={alert.created_at} /></span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{alert.description}</p>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/50 px-3 py-2">
            <span className="text-xs"><span className="font-medium">Suggested action:</span> {alert.suggested_action}</span>
            <Button variant="outline" size="sm" onClick={onResolve}>
              <CheckCheck /> Mark resolved
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
