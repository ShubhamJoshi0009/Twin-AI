"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { motion } from "framer-motion";
import { Activity, CircleDollarSign, RefreshCw, Radar, Route, Sparkles, TrendingUp, Users } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { KPICard } from "@/components/kpi/kpi-card";
import TwinNode, { type TwinNodeType } from "@/components/twin/twin-node";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useInterval } from "@/hooks/use-interval";
import { useMounted } from "@/hooks/use-mounted";
import { useHealth, useTwins } from "@/hooks/use-api";
import { SourceChecklist } from "@/components/profile/source-checklist";
import { SourceOverview } from "@/components/profile/source-overview";
import { formatCurrency, formatNumber } from "@/lib/utils";

const nodeTypes = { twin: TwinNode };

/** Build the digital-twin graph from a live twin record. */
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/60 px-2.5 py-1.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function buildGraph(
  twin: { revenue?: number; profit?: number; customers?: number; employees?: number; market_share?: number }
): { nodes: TwinNodeType[]; edges: Edge[] } {
  const nodes: TwinNodeType[] = [
    { id: "business", type: "twin", position: { x: 380, y: 250 }, data: { label: "Business", type: "business", value: twin.revenue ? formatCurrency(twin.revenue, { compact: true }) : undefined, health: 72 } },
    { id: "finance", type: "twin", position: { x: 380, y: 40 }, data: { label: "Finance", type: "finance", value: formatCurrency(twin.profit, { compact: true }), health: 78 } },
    { id: "sales", type: "twin", position: { x: 640, y: 250 }, data: { label: "Sales", type: "sales", value: formatCurrency(twin.revenue, { compact: true }), health: 74 } },
    { id: "products", type: "twin", position: { x: 120, y: 250 }, data: { label: "Products", type: "products", value: "24 SKUs", health: 69 } },
    { id: "customers", type: "twin", position: { x: 640, y: 450 }, data: { label: "Customers", type: "customers", value: formatNumber(twin.customers), health: 68 } },
    { id: "employees", type: "twin", position: { x: 120, y: 450 }, data: { label: "Employees", type: "employees", value: formatNumber(twin.employees), health: 82 } },
    { id: "suppliers", type: "twin", position: { x: -80, y: 350 }, data: { label: "Suppliers", type: "suppliers", value: "4 active", health: 61 } },
    { id: "warehouses", type: "twin", position: { x: 900, y: 350 }, data: { label: "Warehouses", type: "warehouses", value: "3 facilities", health: 71 } },
  ];

  const link = (source: string, target: string, label?: string): Edge => ({
    id: `${source}-${target}`,
    source,
    target,
    type: "smoothstep",
    animated: true,
    label,
    style: { stroke: "hsl(var(--primary) / 0.35)", strokeWidth: 1.5 },
    labelStyle: { fill: "hsl(var(--muted-foreground))", fontSize: 10 },
    markerEnd: { type: MarkerType.ArrowClosed, color: "hsl(var(--primary) / 0.4)", width: 14, height: 14 },
  });

  const edges: Edge[] = [
    link("business", "finance", "capital"),
    link("business", "sales", "revenue"),
    link("business", "products", "catalog"),
    link("business", "customers", "demand"),
    link("business", "employees", "workforce"),
    link("business", "suppliers", "procurement"),
    link("business", "warehouses", "distribution"),
    link("suppliers", "warehouses", "inbound"),
    link("warehouses", "customers", "fulfillment"),
    link("sales", "customers", "acquisition"),
    link("products", "suppliers", "materials"),
  ];

  return { nodes, edges };
}

export default function DigitalTwinPage() {
  const { data: twins } = useTwins();
  const [selectedTwinId, setSelectedTwinId] = useState<string | null>(null);
  // The selected profile drives the graph, KPIs, health, and source checklist.
  const twin = twins?.find((t) => t.id === selectedTwinId) ?? twins?.[0];
  const twinId = twin?.id ?? null;
  const { data: health } = useHealth(twinId);

  const [view, setView] = useState<"full" | "business" | "sc">("full");
  const [selected, setSelected] = useState<TwinNodeType | null>(null);
  const [pulse, setPulse] = useState(0);

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => buildGraph(twin ?? { revenue: 0, profit: 0, customers: 0, employees: 0, market_share: 0 }), [twin]);
  const [nodes, setNodes, onNodesChange] = useNodesState<TwinNodeType>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdges);

  // Sync when the twin record arrives or the selected profile changes.
  useEffect(() => {
    const { nodes: n, edges: e } = buildGraph(twin ?? { revenue: 0, profit: 0, customers: 0, employees: 0, market_share: 0 });
    setNodes(n);
    setEdges(e);
  }, [twin, setNodes, setEdges]);

  // Reset the node inspector when switching profiles.
  useEffect(() => {
    setSelected(null);
  }, [twinId]);

  // Real-time updates: gently jitter node health every 8s to simulate live telemetry.
  useInterval(() => {
    setPulse((p) => p + 1);
    setNodes((nds) =>
      nds.map((n) =>
        n.data.type === "business" ? n : { ...n, data: { ...n.data, health: Math.max(40, Math.min(98, (n.data.health ?? 70) + (Math.random() * 6 - 3))) } }
      )
    );
  }, 8000);

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => setSelected(node as TwinNodeType), []);
  const mounted = useMounted();

  // View filtering for "relationship view".
  const visibleEdges = useMemo(() => {
    if (view === "full") return edges;
    if (view === "business") return edges.filter((e) => e.source === "business");
    return edges.filter((e) => ["suppliers", "warehouses", "products"].includes(e.source) || ["suppliers", "warehouses"].includes(e.target));
  }, [edges, view]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Digital Twin"
        description="Interactive representation of the enterprise — select a profile and a node to inspect it"
        actions={
          <>
            {(twins ?? []).length > 1 && (
              <Select value={twinId ?? undefined} onValueChange={setSelectedTwinId}>
                <SelectTrigger className="w-[220px]" aria-label="Select business profile">
                  <SelectValue placeholder="Select profile" />
                </SelectTrigger>
                <SelectContent>
                  {(twins ?? []).map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name} · {t.industry}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Tabs value={view} onValueChange={(v) => setView(v as typeof view)}>
              <TabsList>
                <TabsTrigger value="full"><Route /> Full view</TabsTrigger>
                <TabsTrigger value="business"><Activity /> Business</TabsTrigger>
                <TabsTrigger value="sc"><Radar /> Supply chain</TabsTrigger>
              </TabsList>
            </Tabs>
            <Button variant="outline" size="sm" onClick={() => setPulse((p) => p + 1)}>
              <RefreshCw className={pulse % 2 ? "animate-spin" : ""} /> Live
            </Button>
          </>
        }
      />

      {/* KPI row — live snapshot of the twin */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KPICard label="Business Health" value={`${health?.overall_score ?? twin?.business_health_score ?? 0}`} icon={Activity} delta={null} deltaLabel={`Trend: ${health?.trend ?? "—"}`} />
        <KPICard label="Revenue" value={formatCurrency(twin?.revenue, { compact: true })} icon={CircleDollarSign} delta={null} deltaLabel={`${twin?.industry ?? "—"} industry`} />
        <KPICard label="Profit" value={formatCurrency(twin?.profit, { compact: true })} icon={TrendingUp} delta={null} deltaLabel="net after expenses" />
        <KPICard label="Customers" value={formatNumber(twin?.customers)} icon={Users} delta={null} deltaLabel={`${formatNumber(twin?.employees)} employees`} />
      </div>

      {/* Cross-profile source coverage — click a profile to select it */}
      {(twins ?? []).length > 1 && (
        <SourceOverview selectedTwinId={twinId} onSelect={setSelectedTwinId} />
      )}

      {/* Data-source provenance for this business profile */}
      <SourceChecklist twinId={twinId} />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Canvas */}
        <Card className="lg:col-span-2">
          <CardContent className="p-0">
            <div className="h-[560px] w-full overflow-hidden rounded-lg">
              {!mounted && <div className="h-[560px] w-full" aria-hidden />}
              {mounted && <ReactFlow
                nodes={nodes}
                edges={visibleEdges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                fitView
                fitViewOptions={{ padding: 0.15 }}
                minZoom={0.4}
                maxZoom={1.6}
                proOptions={{ hideAttribution: true }}
              >
                <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="hsl(var(--muted-foreground) / 0.15)" />
                <Controls showInteractive={false} position="bottom-left" />
                <MiniMap
                  pannable
                  zoomable
                  nodeColor={() => "hsl(var(--primary) / 0.5)"}
                  maskColor="hsl(var(--background) / 0.75)"
                  position="bottom-right"
                  className="!bg-card"
                />
              </ReactFlow>}
            </div>
          </CardContent>
        </Card>

        {/* Inspector panel */}
        <div className="space-y-4">
          {/* Business overview */}
          <Card>
            <CardHeader className="flex-row items-start justify-between space-y-0">
              <div>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Sparkles className="h-4 w-4 text-chart-3" /> Business Overview
                </CardTitle>
                <CardDescription className="text-xs">{twin?.industry ?? "—"} · updated {twin?.updated_at ? new Date(twin.updated_at).toLocaleDateString() : "—"}</CardDescription>
              </div>
              <Badge variant={health ? (health.overall_score >= 70 ? "success" : health.overall_score >= 50 ? "warning" : "destructive") : "secondary"} className="text-[10px]">
                {health?.overall_score ?? twin?.business_health_score ?? 0}/100
              </Badge>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-sm font-semibold">{twin?.name ?? "—"}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{twin?.description ?? "No description yet."}</p>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <Stat label="Market share" value={`${twin?.market_share ?? 0}%`} />
                <Stat label="Cash flow" value={formatCurrency(twin?.cash_flow, { compact: true })} />
                <Stat label="Marketing budget" value={formatCurrency(twin?.marketing_budget, { compact: true })} />
                <Stat label="Created" value={twin?.created_at ? new Date(twin.created_at).toLocaleDateString() : "—"} />
              </div>
              {(health?.suggestions ?? []).length > 0 && (
                <div className="space-y-1.5 rounded-lg border border-primary/20 bg-primary/5 p-3">
                  <p className="text-[11px] font-semibold text-primary">AI suggestions</p>
                  {(health?.suggestions ?? []).slice(0, 3).map((s, i) => (
                    <p key={i} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-muted-foreground">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-primary" /> {s}
                    </p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Node Inspector</CardTitle>
            </CardHeader>
            <CardContent>
              {selected ? (
                <motion.div key={selected.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-lg">🏢</span>
                    <div>
                      <p className="font-semibold">{selected.data.label}</p>
                      <p className="text-xs capitalize text-muted-foreground">{selected.data.type} node</p>
                    </div>
                  </div>
                  {selected.data.value && (
                    <div className="rounded-md bg-muted px-3 py-2">
                      <p className="text-xs text-muted-foreground">Current value</p>
                      <p className="text-lg font-bold tabular-nums">{selected.data.value}</p>
                    </div>
                  )}
                  {selected.data.health !== undefined && (
                    <div>
                      <p className="mb-1 text-xs text-muted-foreground">Node health</p>
                      <div className="h-2 overflow-hidden rounded-full bg-secondary">
                        <motion.div
                          className="h-full rounded-full bg-primary"
                          initial={{ width: 0 }}
                          animate={{ width: `${selected.data.health}%` }}
                          transition={{ duration: 0.6 }}
                        />
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">Telemetry refreshes automatically every 8 seconds to simulate live updates.</p>
                </motion.div>
              ) : (
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <Radar className="h-8 w-8 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">Click any node to inspect its live state and relationships.</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Network Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Nodes</span><Badge variant="secondary">{nodes.length}</Badge></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Relationships</span><Badge variant="secondary">{visibleEdges.length}</Badge></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Live telemetry</span><Badge variant="secondary">8s interval</Badge></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Market share</span><Badge variant="secondary">{twin?.market_share ?? 6.2}%</Badge></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Health score</span><Badge variant="secondary">{health?.overall_score ?? twin?.business_health_score ?? 0}</Badge></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Health trend</span><Badge variant="secondary">{health?.trend ?? "stable"}</Badge></div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
