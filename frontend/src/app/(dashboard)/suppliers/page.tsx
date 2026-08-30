"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { SearchBar } from "@/components/shared/search-bar";
import { StatusBadge } from "@/components/shared/status-badge";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EmptyState } from "@/components/shared/state-views";
import { useSuppliers } from "@/hooks/use-api";
import * as sc from "@/lib/api/supply-chain";
import { errorMessage } from "@/lib/api/client";
import type { Supplier } from "@/lib/types";
import { cn, formatCurrency, shortId } from "@/lib/utils";

const supplierSchema = z.object({
  name: z.string().min(2, "Name is required"),
  location: z.string().min(2, "Location is required"),
  country: z.string().min(2, "Country is required"),
  product_categories: z.string().default(""),
  lead_time_days: z.coerce.number().min(1).max(120),
  cost_per_unit: z.coerce.number().min(0),
  capacity: z.coerce.number().min(1),
  quality_rating: z.coerce.number().min(0).max(5),
});

type SupplierForm = z.infer<typeof supplierSchema>;

function riskBadge(score: number) {
  if (score >= 60) return "critical" as const;
  if (score >= 40) return "high" as const;
  if (score >= 25) return "medium" as const;
  return "low" as const;
}

export default function SuppliersPage() {
  const { data: suppliers, isLoading, refetch } = useSuppliers();
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return (suppliers ?? []).filter(
      (s) => s.name.toLowerCase().includes(q) || s.country.toLowerCase().includes(q) || s.location.toLowerCase().includes(q)
    );
  }, [suppliers, query]);

  const ranked = useMemo(() => [...filtered].sort((a, b) => b.reliability_score - a.reliability_score), [filtered]);

  const handleSave = async (data: SupplierForm, id?: string) => {
    setSaving(true);
    try {
      const payload = {
        ...data,
        product_categories: data.product_categories.split(",").map((c) => c.trim()).filter(Boolean),
      };
      if (id) {
        await sc.updateSupplier(id, payload);
        toast.success("Supplier updated");
      } else {
        await sc.createSupplier(payload);
        toast.success("Supplier created");
      }
      setDialogOpen(false);
      await refetch();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await sc.deleteSupplier(id);
      toast.success("Supplier deleted");
      await refetch();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Supplier Management"
        description="Monitor supplier performance, reliability and risk across the network"
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => refetch()}><RefreshCw /> Refresh</Button>
            <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) setEditing(null); }}>
              <DialogTrigger asChild>
                <Button size="sm" onClick={() => setEditing(null)}><Plus /> Add Supplier</Button>
              </DialogTrigger>
              <SupplierFormDialog supplier={editing} saving={saving} onSave={handleSave} />
            </Dialog>
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <SearchBar value={query} onChange={setQuery} placeholder="Search suppliers…" className="w-full max-w-sm" />
        <Badge variant="secondary">{filtered.length} of {suppliers?.length ?? 0} suppliers</Badge>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-40 animate-pulse rounded-lg bg-muted" />)}
        </div>
      ) : filtered.length === 0 ? (
        <Card><EmptyState title="No suppliers found" description="Try a different search or add a new supplier." /></Card>
      ) : (
        <Tabs defaultValue="list">
          <TabsList>
            <TabsTrigger value="list">Supplier List</TabsTrigger>
            <TabsTrigger value="ranking">Performance Ranking</TabsTrigger>
          </TabsList>

          <TabsContent value="list" className="mt-4">
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Supplier</TableHead>
                      <TableHead className="hidden md:table-cell">Categories</TableHead>
                      <TableHead className="text-right">Lead time</TableHead>
                      <TableHead className="text-right">Cost/unit</TableHead>
                      <TableHead className="text-right">Quality</TableHead>
                      <TableHead className="text-right">Reliability</TableHead>
                      <TableHead>Risk</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell>
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                              {s.name.slice(0, 2).toUpperCase()}
                            </span>
                            <div>
                              <p className="font-medium">{s.name}</p>
                              <p className="text-xs text-muted-foreground">{s.location}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          <div className="flex flex-wrap gap-1">{s.product_categories.slice(0, 2).map((c) => <Badge key={c} variant="secondary" className="text-[10px]">{c}</Badge>)}</div>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{s.lead_time_days}d</TableCell>
                        <TableCell className="text-right tabular-nums">{formatCurrency(s.cost_per_unit)}</TableCell>
                        <TableCell className="text-right tabular-nums">{s.quality_rating.toFixed(1)}</TableCell>
                        <TableCell className="text-right tabular-nums">{Math.round(s.reliability_score * 100)}%</TableCell>
                        <TableCell><SeverityBadge severity={riskBadge(s.risk_score)} /></TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="icon-sm" onClick={() => { setEditing(s); setDialogOpen(true); }} aria-label={`Edit ${s.name}`}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button variant="ghost" size="icon-sm" aria-label={`Delete ${s.name}`}>
                                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Delete {s.name}?</AlertDialogTitle>
                                  <AlertDialogDescription>This removes the supplier from the network. This action cannot be undone.</AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => handleDelete(s.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                                    Delete
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="ranking" className="mt-4 space-y-3">
            {ranked.map((s, i) => (
              <motion.div key={s.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                <Card className="p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">#{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{s.name}</p>
                        <Badge variant="secondary" className="text-[10px]">{shortId(s.id, 10)}</Badge>
                        <SeverityBadge severity={riskBadge(s.risk_score)} />
                      </div>
                      <div className="mt-2 space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className="w-20 shrink-0 text-xs text-muted-foreground">Reliability</span>
                          <Progress value={s.reliability_score * 100} className="h-1.5" indicatorClassName="bg-success" />
                          <span className="w-10 text-right text-xs tabular-nums">{Math.round(s.reliability_score * 100)}%</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="w-20 shrink-0 text-xs text-muted-foreground">Quality</span>
                          <Progress value={(s.quality_rating / 5) * 100} className="h-1.5" />
                          <span className="w-10 text-right text-xs tabular-nums">{s.quality_rating.toFixed(1)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex shrink-0 gap-4 text-xs text-muted-foreground sm:flex-col sm:gap-1 sm:text-right">
                      <span>Lead time <b className="text-foreground tabular-nums">{s.lead_time_days}d</b></span>
                      <span>Capacity <b className="text-foreground tabular-nums">{s.capacity.toLocaleString()}</b></span>
                    </div>
                  </div>
                </Card>
              </motion.div>
            ))}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function SupplierFormDialog({
  supplier,
  saving,
  onSave,
}: {
  supplier: Supplier | null;
  saving: boolean;
  onSave: (data: SupplierForm, id?: string) => Promise<void>;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SupplierForm>({
    resolver: zodResolver(supplierSchema),
    defaultValues: supplier
      ? {
          name: supplier.name,
          location: supplier.location,
          country: supplier.country,
          product_categories: supplier.product_categories.join(", "),
          lead_time_days: supplier.lead_time_days,
          cost_per_unit: supplier.cost_per_unit,
          capacity: supplier.capacity,
          quality_rating: supplier.quality_rating,
        }
      : {
          name: "",
          location: "",
          country: "",
          product_categories: "electronics",
          lead_time_days: 14,
          cost_per_unit: 20,
          capacity: 5000,
          quality_rating: 4.2,
        },
  });

  return (
    <DialogContent className="max-w-lg">
      <DialogHeader>
        <DialogTitle>{supplier ? "Edit Supplier" : "Add Supplier"}</DialogTitle>
        <DialogDescription>
          {supplier ? `Update details for ${supplier.name}.` : "Register a new supplier in the network."}
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit((d) => onSave(d, supplier?.id))} className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="s-name">Supplier name</Label>
          <Input id="s-name" {...register("name")} placeholder="Acme Components" />
          {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-location">Location</Label>
          <Input id="s-location" {...register("location")} placeholder="Shenzhen, China" />
          {errors.location && <p className="text-xs text-destructive">{errors.location.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-country">Country</Label>
          <Input id="s-country" {...register("country")} placeholder="China" />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="s-cats">Product categories (comma separated)</Label>
          <Input id="s-cats" {...register("product_categories")} placeholder="electronics, packaging" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-lead">Lead time (days)</Label>
          <Input id="s-lead" type="number" {...register("lead_time_days")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-cost">Cost per unit ($)</Label>
          <Input id="s-cost" type="number" step="0.01" {...register("cost_per_unit")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-cap">Capacity (units)</Label>
          <Input id="s-cap" type="number" {...register("capacity")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-quality">Quality rating (0–5)</Label>
          <Input id="s-quality" type="number" step="0.1" min={0} max={5} {...register("quality_rating")} />
        </div>
        <DialogFooter className="sm:col-span-2">
          <Button type="submit" disabled={saving}>{saving ? "Saving…" : supplier ? "Save changes" : "Create supplier"}</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
