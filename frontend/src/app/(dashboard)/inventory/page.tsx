"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Boxes, PackageCheck, PackageX, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { SearchBar } from "@/components/shared/search-bar";
import { StatusBadge } from "@/components/shared/status-badge";
import { KPICard } from "@/components/kpi/kpi-card";
import { ChartCard } from "@/components/charts/chart-card";
import { BarChartComponent } from "@/components/charts/bar-chart";
import { LineAreaChart } from "@/components/charts/line-area-chart";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/shared/state-views";
import { useInventory, useInventoryAnomalies } from "@/hooks/use-api";
import * as sc from "@/lib/api/supply-chain";
import { errorMessage } from "@/lib/api/client";
import { mockTimeSeries } from "@/lib/mock/mock-data";
import { formatCurrency, formatNumber } from "@/lib/utils";

export default function InventoryPage() {
  const { data: inventory, isLoading, refetch } = useInventory();
  const { data: anomalies } = useInventoryAnomalies();
  const [query, setQuery] = useState("");
  const [optimizing, setOptimizing] = useState(false);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return (inventory ?? []).filter((i) => i.product_name.toLowerCase().includes(q) || i.product_sku.toLowerCase().includes(q));
  }, [inventory, query]);

  const stockTrend = useMemo(() => mockTimeSeries(6, 12, 480, 0.1), []);
  const fastMoving = useMemo(() => [...(inventory ?? [])].sort((a, b) => b.turnover_rate - a.turnover_rate).slice(0, 5), [inventory]);
  const slowMoving = useMemo(() => [...(inventory ?? [])].sort((a, b) => a.turnover_rate - b.turnover_rate).slice(0, 5), [inventory]);

  const lowStock = (inventory ?? []).filter((i) => i.status !== "healthy").length;
  const stockValue = (inventory ?? []).reduce((sum, i) => sum + i.current_stock * i.unit_cost, 0);

  const handleOptimize = async () => {
    setOptimizing(true);
    try {
      const res = await sc.optimizeInventory();
      toast.success(`Optimization complete — score ${res.optimization_score}`);
      await refetch();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setOptimizing(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inventory Management"
        description="Stock levels, reorder alerts and movement analytics"
        actions={
          <Button variant="outline" size="sm" onClick={handleOptimize} disabled={optimizing}>
            <RefreshCw className={optimizing ? "animate-spin" : ""} /> Run Optimization
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KPICard label="Total SKUs" value={String(inventory?.length ?? 0)} icon={Boxes} delta={null} />
        <KPICard label="Stock value" value={formatCurrency(stockValue, { compact: true })} icon={PackageCheck} delta={null} />
        <KPICard label="Attention needed" value={String(lowStock)} icon={AlertTriangle} delta={null} />
        <KPICard label="Anomalies" value={String(anomalies?.count ?? 0)} icon={PackageX} delta={null} />
      </div>

      {/* Reorder alerts */}
      <Card className="border-warning/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm"><AlertTriangle className="h-4 w-4 text-warning" /> Reorder Alerts</CardTitle>
          <CardDescription className="text-xs">Items at or below reorder thresholds</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(anomalies?.anomalies ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No reorder anomalies — inventory is healthy.</p>
          ) : (
            (anomalies?.anomalies ?? []).map((a, i) => (
              <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center">
                <div className="flex items-center gap-2.5 sm:w-64 sm:shrink-0">
                  <StatusBadge status={a.severity} />
                  <div>
                    <p className="text-sm font-medium">{a.product_name}</p>
                    <p className="text-xs text-muted-foreground">{a.product_sku}</p>
                  </div>
                </div>
                <p className="flex-1 text-sm text-muted-foreground">{a.description}</p>
                <div className="sm:w-56">
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-muted-foreground">Stock</span>
                    <span className="tabular-nums">{formatNumber(a.current_stock)}</span>
                  </div>
                  <Progress value={a.current_stock} max={200} className="h-1.5" indicatorClassName="bg-destructive" />
                </div>
                <Badge variant="secondary" className="shrink-0">{a.recommended_action}</Badge>
              </motion.div>
            ))
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard id="stock-trend" title="Stock Trends" description="Aggregate stock levels over time (modeled)" csvData={stockTrend}>
          <LineAreaChart data={stockTrend} xKey="label" type="area" series={[{ key: "value", name: "Units" }]} formatter={(v) => formatNumber(v)} />
        </ChartCard>
        <ChartCard id="turnover" title="Inventory Turnover" description="Fast vs slow moving items">
          <BarChartComponent
            data={[
              ...fastMoving.map((i) => ({ label: i.product_name, turnover: i.turnover_rate, color: "fast" })),
              ...slowMoving.slice(0, 3).map((i) => ({ label: i.product_name, turnover: i.turnover_rate, color: "slow" })),
            ]}
            xKey="label"
            series={[{ key: "turnover", name: "Turnover rate" }]}
            formatter={(v) => `${v.toFixed(1)}x`}
          />
        </ChartCard>
      </div>

      {/* Inventory table */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm">Inventory List</CardTitle>
          <SearchBar value={query} onChange={setQuery} placeholder="Search products…" className="w-56" />
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-3 p-5">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />)}</div>
          ) : filtered.length === 0 ? (
            <EmptyState title="No inventory items" description="Try a different search term." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead className="hidden md:table-cell">Warehouse</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="hidden sm:table-cell text-right">Available</TableHead>
                  <TableHead className="text-right">Unit cost</TableHead>
                  <TableHead className="text-right">Turnover</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((i) => (
                  <TableRow key={i.id}>
                    <TableCell>
                      <p className="font-medium">{i.product_name}</p>
                      <p className="text-xs text-muted-foreground">{i.product_sku}</p>
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground md:table-cell">{i.warehouse_id.slice(0, 8)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(i.current_stock)}</TableCell>
                    <TableCell className="hidden text-right tabular-nums text-muted-foreground sm:table-cell">{formatNumber(i.available_stock)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(i.unit_cost)}</TableCell>
                    <TableCell className="text-right tabular-nums">{i.turnover_rate.toFixed(1)}x</TableCell>
                    <TableCell><StatusBadge status={i.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
