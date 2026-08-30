"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  Factory,
  PackageCheck,
  ShieldAlert,
  Ship,
  Truck,
  Warehouse as WarehouseIcon,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { KPICard } from "@/components/kpi/kpi-card";
import { Gauge } from "@/components/charts/gauge";
import { ChartCard } from "@/components/charts/chart-card";
import { BarChartComponent } from "@/components/charts/bar-chart";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { SkeletonGrid } from "@/components/shared/state-views";
import { useAlerts, useInventory, useOptimization, useRisks, useSCHealth, useShipments, useSuppliers, useWarehouses } from "@/hooks/use-api";
import { formatCurrency, formatNumber } from "@/lib/utils";

export default function SupplyChainPage() {
  const [tab, setTab] = useState("overview");
  const { data: scHealth } = useSCHealth();
  const { data: suppliers } = useSuppliers();
  const { data: warehouses } = useWarehouses();
  const { data: inventory } = useInventory();
  const { data: shipments } = useShipments();
  const { data: risks } = useRisks();
  const { data: alerts } = useAlerts();
  const { data: optimization } = useOptimization();

  const kpis = useMemo(() => ({
    suppliers: suppliers?.length ?? 0,
    warehouses: warehouses?.length ?? 0,
    inventoryItems: inventory?.length ?? 0,
    inTransit: shipments?.filter((s) => s.status === "in_transit").length ?? 0,
    delayed: shipments?.filter((s) => s.status === "delayed").length ?? 0,
    activeRisks: risks?.filter((r) => r.status === "active").length ?? 0,
    activeAlerts: alerts?.filter((a) => a.status === "active").length ?? 0,
  }), [suppliers, warehouses, inventory, shipments, risks, alerts]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Supply Chain"
        description="End-to-end visibility across suppliers, inventory, warehouses, logistics and risk"
        actions={
          <>
            <Button asChild variant="outline" size="sm"><Link href="/alerts"><AlertTriangle /> Alerts ({kpis.activeAlerts})</Link></Button>
            <Button asChild size="sm"><Link href="/logistics"><Ship /> Logistics</Link></Button>
          </>
        }
      />

      {/* KPI row */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KPICard label="Suppliers" value={String(kpis.suppliers)} icon={Truck} delta={null} description="Active supplier network" index={0} />
        <KPICard label="Warehouses" value={String(kpis.warehouses)} icon={WarehouseIcon} delta={null} description="Operational facilities" index={1} />
        <KPICard label="Inventory SKUs" value={String(kpis.inventoryItems)} icon={Boxes} delta={null} description="Tracked products" index={2} />
        <KPICard label="Shipments" value={formatNumber(kpis.inTransit + kpis.delayed)} icon={Ship} delta={null} description={`${kpis.inTransit} in transit · ${kpis.delayed} delayed`} index={3} />
      </div>

      {/* Health + risk */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="flex flex-col items-center justify-center p-5">
          <Gauge value={scHealth?.overall_score ?? 0} label="Supply Chain Health" sublabel={`Trend: ${scHealth?.trend}`} />
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm"><ShieldAlert className="h-4 w-4 text-chart-3" /> Category Health</CardTitle>
            <CardDescription className="text-xs">Sub-scores across the supply chain</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(scHealth?.category_scores ?? {}).map(([k, v]) => (
              <div key={k} className="flex items-center gap-3">
                <span className="w-36 shrink-0 truncate text-sm">{k.replace(/_/g, " ")}</span>
                <Progress value={v} className="h-2 min-w-0 flex-1" indicatorClassName={v >= 70 ? "bg-success" : v >= 50 ? "bg-warning" : "bg-destructive"} />
                <span className="w-10 shrink-0 text-right text-sm font-medium tabular-nums">{v.toFixed(0)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="suppliers">Suppliers</TabsTrigger>
          <TabsTrigger value="warehouses">Warehouses</TabsTrigger>
          <TabsTrigger value="inventory">Inventory</TabsTrigger>
          <TabsTrigger value="shipments">Shipments</TabsTrigger>
          <TabsTrigger value="risks">Risks</TabsTrigger>
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
          <TabsTrigger value="optimization">Optimization</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4 space-y-4">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MiniStat icon={Factory} label="Warehouse utilization" value={`${Math.round(((warehouses ?? [])[0]?.utilization ?? 0) * 100)}%`} sub="East Coast DC at 84%" />
            <MiniStat icon={PackageCheck} label="Inventory health" value={`${inventory?.filter((i) => i.status === "healthy").length ?? 0}/${inventory?.length ?? 0}`} sub="SKUs healthy" />
            <MiniStat icon={Ship} label="Route efficiency" value="86%" sub="Optimized routes" />
            <MiniStat icon={AlertTriangle} label="Active alerts" value={String(kpis.activeAlerts)} sub={`${kpis.activeRisks} active risks`} />
          </div>
          <ChartCard id="sc-risk-dist" title="Risk Distribution" description="Active risks by severity" height={260}>
            <BarChartComponent
              data={[
                { label: "Critical", count: (risks ?? []).filter((r) => r.severity === "critical").length },
                { label: "High", count: (risks ?? []).filter((r) => r.severity === "high").length },
                { label: "Medium", count: (risks ?? []).filter((r) => r.severity === "medium").length },
                { label: "Low", count: (risks ?? []).filter((r) => r.severity === "low").length },
              ]}
              xKey="label"
              series={[{ key: "count", name: "Risks" }]}
              formatter={(v) => String(v)}
              singleColor
            />
          </ChartCard>
        </TabsContent>

        <TabsContent value="suppliers" className="mt-4">
          <TableCard title="Supplier Overview" action={<Button asChild variant="ghost" size="sm"><Link href="/suppliers">Manage suppliers <ArrowRight /></Link></Button>}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Supplier</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead className="text-right">Lead time</TableHead>
                  <TableHead className="text-right">Cost/unit</TableHead>
                  <TableHead className="text-right">Quality</TableHead>
                  <TableHead className="text-right">Reliability</TableHead>
                  <TableHead className="text-right">Risk</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(suppliers ?? []).slice(0, 6).map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell className="text-muted-foreground">{s.country}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.lead_time_days}d</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(s.cost_per_unit)}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.quality_rating.toFixed(1)}</TableCell>
                    <TableCell className="text-right tabular-nums">{Math.round(s.reliability_score * 100)}%</TableCell>
                    <TableCell className="text-right"><SeverityBadge severity={s.risk_score > 60 ? "critical" : s.risk_score > 40 ? "high" : s.risk_score > 25 ? "medium" : "low"} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableCard>
        </TabsContent>

        <TabsContent value="warehouses" className="mt-4">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {(warehouses ?? []).map((w, i) => (
              <motion.div key={w.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <Card className="h-full">
                  <CardHeader className="flex-row items-center justify-between space-y-0">
                    <div>
                      <CardTitle className="text-sm">{w.name}</CardTitle>
                      <CardDescription className="text-xs">{w.location}</CardDescription>
                    </div>
                    <WarehouseIcon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent className="space-y-2.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Utilization</span>
                      <span className="font-semibold tabular-nums">{Math.round(w.utilization * 100)}%</span>
                    </div>
                    <Progress value={w.utilization * 100} indicatorClassName={w.utilization > 0.85 ? "bg-warning" : "bg-primary"} />
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Capacity: {formatNumber(w.capacity, { compact: true })}</span>
                      <span>Efficiency: {w.efficiency_score}</span>
                    </div>
                    <div className="flex gap-2 pt-1">
                      <Badge variant="secondary">{w.incoming_shipments} inbound</Badge>
                      <Badge variant="secondary">{w.outgoing_shipments} outbound</Badge>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="inventory" className="mt-4">
          <TableCard title="Stock Levels" action={<Button asChild variant="ghost" size="sm"><Link href="/inventory">Inventory analytics <ArrowRight /></Link></Button>}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>SKU</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-right">Reorder level</TableHead>
                  <TableHead className="text-right">Unit cost</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(inventory ?? []).slice(0, 6).map((i) => (
                  <TableRow key={i.id}>
                    <TableCell className="font-medium">{i.product_name}</TableCell>
                    <TableCell className="text-muted-foreground">{i.product_sku}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(i.current_stock)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(i.reorder_level)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(i.unit_cost)}</TableCell>
                    <TableCell><StatusBadge status={i.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableCard>
        </TabsContent>

        <TabsContent value="shipments" className="mt-4">
          <TableCard title="Shipment Status" action={<Button asChild variant="ghost" size="sm"><Link href="/logistics">Track logistics <ArrowRight /></Link></Button>}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Shipment</TableHead>
                  <TableHead>Route</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Distance</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(shipments ?? []).slice(0, 6).map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.shipment_number}</TableCell>
                    <TableCell className="max-w-52 truncate text-muted-foreground">{s.origin} → {s.destination}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(s.quantity)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(s.distance_km)} km</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(s.transport_cost, { compact: true })}</TableCell>
                    <TableCell><StatusBadge status={s.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableCard>
        </TabsContent>

        <TabsContent value="risks" className="mt-4">
          <div className="grid gap-3 md:grid-cols-2">
            {(risks ?? []).map((r, i) => (
              <motion.div key={r.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                <Card className="h-full">
                  <CardContent className="flex items-start gap-3 p-4">
                    <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
                      <ShieldAlert className="h-4 w-4 text-destructive" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium">{r.title}</p>
                        <SeverityBadge severity={r.severity} />
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{r.description}</p>
                      <p className="mt-2 text-xs text-muted-foreground">Risk score: <span className="font-semibold tabular-nums text-foreground">{Math.round(r.risk_score * 100) / 100}</span> · {Math.round(r.probability * 100)}% probability</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="alerts" className="mt-4">
          <TableCard title="Active Alerts" action={<Button asChild variant="ghost" size="sm"><Link href="/alerts">Alerts center <ArrowRight /></Link></Button>}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Alert</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead className="hidden md:table-cell">Suggested action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(alerts ?? []).slice(0, 6).map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <p className="font-medium">{a.title}</p>
                      <p className="line-clamp-1 text-xs text-muted-foreground">{a.description}</p>
                    </TableCell>
                    <TableCell className="capitalize text-muted-foreground">{a.alert_type}</TableCell>
                    <TableCell><SeverityBadge severity={a.severity} /></TableCell>
                    <TableCell className="hidden max-w-60 truncate text-xs text-muted-foreground md:table-cell">{a.suggested_action}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableCard>
        </TabsContent>

        <TabsContent value="optimization" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Optimization Opportunities</CardTitle>
              <CardDescription className="text-xs">
                Total potential saving: <span className="font-semibold text-success">{formatCurrency(optimization?.total_potential_saving, { compact: true })}</span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(optimization?.recommendations ?? []).map((r, i) => (
                <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="flex items-center gap-3 rounded-lg border p-3">
                  <Badge variant={r.priority === "high" ? "critical" : "warning"} className="w-16 justify-center capitalize">{r.priority}</Badge>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{r.recommendation}</p>
                    <p className="text-xs capitalize text-muted-foreground">{r.category}</p>
                  </div>
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-success">{formatCurrency(r.potential_saving, { compact: true })}</span>
                </motion.div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MiniStat({ icon: Icon, label, value, sub }: { icon: typeof Truck; label: string; value: string; sub: string }) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-lg font-bold leading-tight tabular-nums">{value}</p>
        <p className="truncate text-[11px] text-muted-foreground">{sub}</p>
      </div>
    </Card>
  );
}

function TableCard({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm">{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent className="p-0">{children}</CardContent>
    </Card>
  );
}
