"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, CircleDashed, Map as MapIcon, MapPin, RefreshCw, Ship, Timer, Truck, Wallet } from "lucide-react";
import { ShipmentRouteMap } from "@/components/logistics/route-map";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { KPICard } from "@/components/kpi/kpi-card";
import { ChartCard } from "@/components/charts/chart-card";
import { BarChartComponent } from "@/components/charts/bar-chart";
import { LineAreaChart } from "@/components/charts/line-area-chart";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/shared/state-views";
import { useShipments } from "@/hooks/use-api";
import * as sc from "@/lib/api/supply-chain";
import { errorMessage } from "@/lib/api/client";
import { mockTimeSeries } from "@/lib/mock/mock-data";
import { cn, formatCurrency, formatDate, formatNumber } from "@/lib/utils";
import type { Shipment } from "@/lib/types";

const TIMELINE_STEPS = ["Pickup", "In transit", "Customs / Port", "Regional hub", "Final delivery"];

export default function LogisticsPage() {
  const { data: shipments, isLoading, refetch } = useShipments();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [optimizing, setOptimizing] = useState(false);

  const selected = shipments?.find((s) => s.id === selectedId) ?? shipments?.[0] ?? null;

  const counts = useMemo(() => ({
    inTransit: shipments?.filter((s) => s.status === "in_transit").length ?? 0,
    delivered: shipments?.filter((s) => s.status === "delivered").length ?? 0,
    delayed: shipments?.filter((s) => s.status === "delayed").length ?? 0,
    pending: shipments?.filter((s) => s.status === "pending").length ?? 0,
  }), [shipments]);

  const totalCost = useMemo(() => (shipments ?? []).reduce((s, x) => s + x.transport_cost + x.fuel_cost, 0), [shipments]);
  const costSeries = useMemo(() => mockTimeSeries(7, 12, 9.4, 0.08), []);
  const perfSeries = useMemo(() => mockTimeSeries(8, 12, 88, 0.03), []);

  const handleOptimizeRoutes = async () => {
    setOptimizing(true);
    try {
      const res = await sc.optimizeRoutes();
      toast.success(`Routes optimized — ${res.routes.length} routes updated`);
      await refetch();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setOptimizing(false);
    }
  };

  const stepIndex = selected?.status === "delivered" ? 4 : selected?.status === "delayed" ? 2 : selected?.status === "in_transit" ? 1 : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Logistics Dashboard"
        description="Shipment tracking, route status and transportation costs"
        actions={
          <Button variant="outline" size="sm" onClick={handleOptimizeRoutes} disabled={optimizing}>
            <RefreshCw className={optimizing ? "animate-spin" : ""} /> Optimize Routes
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KPICard label="In transit" value={String(counts.inTransit)} icon={Truck} delta={null} />
        <KPICard label="Delivered" value={String(counts.delivered)} icon={CheckCircle2} delta={null} />
        <KPICard label="Delayed" value={String(counts.delayed)} icon={Timer} delta={null} />
        <KPICard label="Transport cost" value={formatCurrency(totalCost, { compact: true })} icon={Wallet} delta={null} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Shipment table */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="text-sm">Shipment Tracking</CardTitle>
              <CardDescription className="text-xs">Select a shipment to view its route timeline</CardDescription>
            </div>
            <Badge variant="secondary">{shipments?.length ?? 0} shipments</Badge>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="space-y-3 p-5">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-11 animate-pulse rounded-md bg-muted" />)}</div>
            ) : (shipments ?? []).length === 0 ? (
              <EmptyState title="No shipments" description="Shipments will appear here once created." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Shipment</TableHead>
                    <TableHead className="hidden md:table-cell">Product</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead className="hidden sm:table-cell">Route</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(shipments ?? []).map((s) => (
                    <TableRow
                      key={s.id}
                      className={cn("cursor-pointer", selected?.id === s.id && "bg-primary/5")}
                      onClick={() => setSelectedId(s.id)}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Ship className={cn("h-4 w-4", s.status === "delayed" ? "text-destructive" : "text-muted-foreground")} />
                          <div>
                            <p className="font-medium">{s.shipment_number}</p>
                            <p className="text-xs text-muted-foreground">{formatDate(s.created_at)}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">{s.product_name}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatNumber(s.quantity)}</TableCell>
                      <TableCell className="hidden max-w-48 truncate text-xs text-muted-foreground sm:table-cell">{s.origin} → {s.destination}</TableCell>
                      <TableCell><StatusBadge status={s.status} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Route map + timeline */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <MapIcon className="h-4 w-4 text-chart-3" /> Route Map
              </CardTitle>
              <CardDescription className="text-xs">
                {selected ? `${selected.origin} → ${selected.destination}` : "Select a shipment to see its route"}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-3">
              {selected ? (
                <ShipmentRouteMap
                  origin={selected.origin}
                  destination={selected.destination}
                  distanceKm={selected.distance_km}
                  className="h-56"
                />
              ) : (
                <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
                  <MapPin className="mr-2 h-4 w-4" /> Select a shipment to preview its route
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Delivery Timeline</CardTitle>
              <CardDescription className="text-xs">{selected ? `${selected.shipment_number} — ${selected.origin} → ${selected.destination}` : "No shipment selected"}</CardDescription>
            </CardHeader>
            <CardContent>
              {selected ? (
                <ol className="relative space-y-4 border-l border-border pl-5">
                  {TIMELINE_STEPS.map((step, i) => {
                    const done = i <= stepIndex;
                    return (
                      <li key={step} className="relative">
                        <span className={cn("absolute -left-[26px] top-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2", done ? "border-primary bg-primary/20" : "border-border bg-card")}>
                          {done && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
                        </span>
                        <p className={cn("text-sm", done ? "font-medium" : "text-muted-foreground")}>{step}</p>
                        {i === stepIndex && <Badge variant="secondary" className="ml-2 text-[10px] capitalize">current: {selected.status}</Badge>}
                      </li>
                    );
                  })}
                </ol>
              ) : (
                <p className="text-sm text-muted-foreground">Select a shipment to see its timeline.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Cost & performance */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard id="transport-cost" title="Transportation Cost" description="Monthly transport spend (modeled)" csvData={costSeries}>
          <BarChartComponent data={costSeries} xKey="label" series={[{ key: "value", name: "Cost ($k)" }]} formatter={(v) => formatCurrency(v * 1000, { compact: true })} />
        </ChartCard>
        <ChartCard id="delivery-perf" title="Delivery Performance" description="On-time delivery rate (modeled)" csvData={perfSeries}>
          <LineAreaChart data={perfSeries} xKey="label" type="area" series={[{ key: "value", name: "On-time %" }]} formatter={(v) => `${v.toFixed(1)}%`} />
        </ChartCard>
      </div>
    </div>
  );
}
