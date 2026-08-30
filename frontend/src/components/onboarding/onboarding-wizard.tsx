"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Building2,
  Check,
  CircleDollarSign,
  LayoutDashboard,
  Loader2,
  Rocket,
  Sparkles,
  TrendingUp,
  Truck,
  Users,
  Warehouse,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { getSeedStatus, applySeedData } from "@/lib/api/system";
import { useProfileStore } from "@/stores/profile-store";
import { cn } from "@/lib/utils";

/* ── Steps ────────────────────────────────────────────────────────────────── */

const INDUSTRIES = [
  "technology", "retail", "manufacturing", "food_retail", "healthcare",
  "finance", "logistics", "energy", "education", "real_estate", "other",
] as const;

const INDUSTRY_LABELS: Record<string, string> = {
  technology: "Technology / SaaS",
  retail: "Retail & E-commerce",
  manufacturing: "Manufacturing",
  food_retail: "Food & Grocery",
  healthcare: "Healthcare",
  finance: "Finance",
  logistics: "Logistics & Supply Chain",
  energy: "Energy",
  education: "Education",
  real_estate: "Real Estate",
  other: "Other",
};

interface StepProps {
  step: number;
  setStep: (s: number) => void;
  form: Record<string, unknown>;
  setForm: (patch: Record<string, unknown>) => void;
  onNext: () => void;
  submitting: boolean;
}

/* ── Main wizard ───────────────────────────────────────────────────────────── */

export function OnboardingWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<Record<string, unknown>>({
    name: "",
    industry: "technology",
    description: "",
    revenue: 5_000_000,
    expenses: 3_500_000,
    cash_flow: 800_000,
    customers: 500,
    employees: 60,
    sales: 4_200_000,
    marketing_budget: 300_000,
    market_share: 4.5,
    growth_rate: 12,
    churn_rate: 3.5,
    customer_lifetime_value: 2400,
    nps_score: 42,
    // Optional supply chain quick-start
    suppliers: [
      { name: "", location: "", country: "" },
    ],
    warehouses: [
      { name: "", location: "" },
    ],
  });
  const [submitting, setSubmitting] = useState(false);
  const [confirmReplace, setConfirmReplace] = useState(false);

  const setPatch = (patch: Record<string, unknown>) => setForm((f) => ({ ...f, ...patch }));

  const validateStep = (s: number): string | null => {
    if (s === 0) {
      if (!String(form.name).trim()) return "Give your company a name to get started.";
      return null;
    }
    if (s === 1) {
      if (Number(form.revenue) < 0 || Number(form.expenses) < 0) return "Revenue and expenses must be positive.";
      if (Number(form.expenses) > Number(form.revenue) * 1.5) return "Expenses look very high versus revenue — double-check the numbers.";
      return null;
    }
    if (s === 2) {
      if (Number(form.customers) <= 0) return "Enter your current customer count.";
      return null;
    }
    if (s === 3) {
      if (Number(form.growth_rate) < -50 || Number(form.growth_rate) > 500) return "Growth rate looks out of range.";
      return null;
    }
    return null;
  };

  const handleNext = () => {
    const err = validateStep(step);
    if (err) {
      toast.warning(err);
      return;
    }
    setStep((s) => Math.min(s + 1, 4));
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload = buildSeedPayload(form);
      const res = await applySeedData(payload, true);
      if (res.skipped) {
        toast.info(res.reason ?? "Nothing to do — data already present.");
      } else {
        toast.success(`Created digital twin: ${res.twin?.name ?? "your business"}`);
      }
      // Keep the AI assistant's profile in sync so the whole workspace
      // (greetings, suggestions, topbar, settings) reflects this company.
      // Status stays "collecting" so the assistant still nudges the user
      // to complete their personal profile conversationally.
      useProfileStore.getState().replaceProfile(
        {
          name: String(form.name).trim(),
          industry: String(form.industry ?? ""),
          industryLabel: INDUSTRY_LABELS[String(form.industry)] ?? "",
          employees: Number(form.employees ?? 0),
          revenue: Number(form.revenue ?? 0),
          description: String(form.description ?? ""),
        },
        {}
      );
      useProfileStore.getState().setStatus("collecting");
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create your twin");
      setSubmitting(false);
    }
  };

  // If the database already contains data, ask before replacing it.
  const handleFinalize = async () => {
    setSubmitting(true);
    try {
      const status = await getSeedStatus();
      if (status.has_data) {
        setConfirmReplace(true);
        setSubmitting(false);
        return;
      }
      await handleSubmit();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to check database");
      setSubmitting(false);
    }
  };

  const steps = [
    { label: "Company", icon: Building2 },
    { label: "Finances", icon: CircleDollarSign },
    { label: "Market", icon: Users },
    { label: "Growth", icon: TrendingUp },
    { label: "Supply Chain", icon: Truck },
  ];

  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      {/* Ambient gradient backdrop */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-primary/20 blur-3xl" />
        <div className="absolute bottom-0 right-1/4 h-96 w-96 rounded-full bg-violet-600/10 blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(56,189,248,0.06),transparent_55%)]" />
      </div>

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col px-4 py-8 sm:px-8">
        {/* Header */}
        <header className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 shadow-lg">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-bold leading-tight">Business Twin AI</p>
              <p className="text-[11px] text-muted-foreground">Intelligence Platform</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" asChild>
            <span role="link" onClick={() => router.push("/dashboard")} className="gap-2">
              <LayoutDashboard className="h-4 w-4" /> Skip to dashboard
            </span>
          </Button>
        </header>

        <div className="grid flex-1 items-center gap-10 lg:grid-cols-[1.1fr_1fr]">
          {/* Left: pitch + step rail */}
          <div className="space-y-6">
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
              <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary">
                <Sparkles className="h-3.5 w-3.5" /> Build your digital twin in 2 minutes
              </div>
              <h1 className="text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
                Model your company&apos;s{" "}
                <span className="bg-gradient-to-r from-blue-500 via-violet-500 to-fuchsia-500 bg-clip-text text-transparent">
                  future growth
                </span>
                , before you commit.
              </h1>
              <p className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
                Tell us about your business — finances, customers, market and growth targets. We
                build an AI digital twin that forecasts outcomes, simulates decisions and watches
                live market news for you.
              </p>
            </motion.div>

            {/* Step rail */}
            <div className="space-y-2">
              {steps.map((s, i) => {
                const Icon = s.icon;
                const active = i === step;
                const done = i < step;
                return (
                  <button
                    key={s.label}
                    onClick={() => i < step && setStep(i)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all duration-200",
                      active
                        ? "border-primary/40 bg-primary/10 shadow-sm"
                        : done
                          ? "border-border/60 bg-card/60 hover:border-primary/30"
                          : "border-border/40 bg-card/40 opacity-70"
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors",
                        active ? "bg-primary text-primary-foreground" : done ? "bg-success/15 text-success" : "bg-muted text-muted-foreground"
                      )}
                    >
                      {done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className={cn("text-sm font-medium", active ? "text-foreground" : "text-muted-foreground")}>{s.label}</p>
                      <p className="truncate text-[11px] text-muted-foreground/70">{stepDescription(i)}</p>
                    </div>
                    {active && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: form card */}
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
            <Card className="relative overflow-hidden shadow-2xl">
              <div className="h-1 w-full bg-gradient-to-r from-blue-500 via-violet-500 to-fuchsia-500">
                <motion.div
                  className="h-full bg-white/60"
                  initial={false}
                  animate={{ width: `${((step + 1) / steps.length) * 100}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
              <CardContent className="p-6 sm:p-8">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={step}
                    initial={{ opacity: 0, x: 24 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -24 }}
                    transition={{ duration: 0.25 }}
                  >
                    {step === 0 && <CompanyStep form={form} setForm={setPatch} />}
                    {step === 1 && <FinanceStep form={form} setForm={setPatch} />}
                    {step === 2 && <MarketStep form={form} setForm={setPatch} />}
                    {step === 3 && <GrowthStep form={form} setForm={setPatch} />}
                    {step === 4 && <SupplyChainStep form={form} setForm={setPatch} />}
                  </motion.div>
                </AnimatePresence>

                {/* Footer nav */}
                <div className="mt-8 flex items-center justify-between gap-3 border-t pt-5">
                  <Button variant="ghost" size="sm" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0 || submitting} className="gap-2">
                    <ArrowLeft className="h-4 w-4" /> Back
                  </Button>
                  {step < 4 ? (
                    <Button size="sm" onClick={handleNext} className="gap-2">
                      Continue <ArrowRight className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button size="sm" onClick={handleFinalize} disabled={submitting} className="gap-2 bg-gradient-to-r from-blue-500 to-violet-600 hover:from-blue-600 hover:to-violet-700">
                      {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
                      {submitting ? "Creating your twin…" : "Create Digital Twin"}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
      {/* Replace-existing confirmation */}
      <AlertDialog open={confirmReplace} onOpenChange={setConfirmReplace}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Replace existing data?</AlertDialogTitle>
            <AlertDialogDescription>
              Your database already contains a digital twin and supply chain data. Creating this new
              twin will <b>replace it</b> — the previous dataset will be wiped.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={submitting}
              onClick={(e) => { e.preventDefault(); handleSubmit(); }}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Replace & Create Twin
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function stepDescription(i: number) {
  return [
    "Name, industry & description",
    "Revenue, costs & cash flow",
    "Customers, team & market share",
    "Growth rate, retention & NPS",
    "Optional suppliers & warehouses",
  ][i];
}

/* ── Field primitives ──────────────────────────────────────────────────────── */

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium text-muted-foreground">{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground/70">{hint}</p>}
    </div>
  );
}

function MoneyInput({ value, onChange, placeholder }: { value: unknown; onChange: (v: number) => void; placeholder?: string }) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
      <Input
        type="number"
        value={Number(value ?? 0)}
        onChange={(e) => onChange(Number(e.target.value))}
        className="pl-7"
        placeholder={placeholder}
      />
    </div>
  );
}

/* ── Step components ───────────────────────────────────────────────────────── */

function CompanyStep({ form, setForm }: { form: Record<string, unknown>; setForm: (p: Record<string, unknown>) => void }) {
  return (
    <div className="space-y-4">
      <StepTitle icon={Building2} title="Tell us about your company" subtitle="This becomes the identity of your digital twin." />
      <Field label="Company name">
        <Input value={String(form.name)} onChange={(e) => setForm({ name: e.target.value })} placeholder="e.g. GreenLeaf Organics" autoFocus />
      </Field>
      <Field label="Industry">
        <Select value={String(form.industry)} onValueChange={(v) => setForm({ industry: v })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {INDUSTRIES.map((i) => (
              <SelectItem key={i} value={i}>{INDUSTRY_LABELS[i]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="Description" hint="One line about what the business does.">
        <Textarea value={String(form.description)} onChange={(e) => setForm({ description: e.target.value })} placeholder="e.g. Organic grocery chain with 6 metro stores and a D2C delivery arm." rows={3} />
      </Field>
    </div>
  );
}

function FinanceStep({ form, setForm }: { form: Record<string, unknown>; setForm: (p: Record<string, unknown>) => void }) {
  const revenue = Number(form.revenue ?? 0);
  const expenses = Number(form.expenses ?? 0);
  const profit = revenue - expenses;
  const margin = revenue > 0 ? (profit / revenue) * 100 : 0;
  return (
    <div className="space-y-4">
      <StepTitle icon={CircleDollarSign} title="Financial snapshot" subtitle="Annual figures — we'll forecast growth from here." />
      <div className="grid grid-cols-2 gap-3">
        <Field label="Annual revenue">
          <MoneyInput value={form.revenue} onChange={(v) => setForm({ revenue: v })} />
        </Field>
        <Field label="Annual expenses">
          <MoneyInput value={form.expenses} onChange={(v) => setForm({ expenses: v })} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Cash flow">
          <MoneyInput value={form.cash_flow} onChange={(v) => setForm({ cash_flow: v })} />
        </Field>
        <Field label="Net sales">
          <MoneyInput value={form.sales} onChange={(v) => setForm({ sales: v })} />
        </Field>
      </div>
      <Field label="Marketing budget (annual)">
        <MoneyInput value={form.marketing_budget} onChange={(v) => setForm({ marketing_budget: v })} />
      </Field>
      <div className={cn("flex items-center justify-between rounded-lg border px-3 py-2 text-xs", profit >= 0 ? "border-success/30 bg-success/10 text-success" : "border-destructive/30 bg-destructive/10 text-destructive")}>
        <span>Estimated profit: <b>{formatMoney(profit)}</b></span>
        <span>{margin.toFixed(1)}% margin</span>
      </div>
    </div>
  );
}

function MarketStep({ form, setForm }: { form: Record<string, unknown>; setForm: (p: Record<string, unknown>) => void }) {
  return (
    <div className="space-y-4">
      <StepTitle icon={Users} title="Your market position" subtitle="Who you serve and how big your footprint is." />
      <div className="grid grid-cols-2 gap-3">
        <Field label="Active customers">
          <Input type="number" value={Number(form.customers ?? 0)} onChange={(e) => setForm({ customers: Number(e.target.value) })} />
        </Field>
        <Field label="Employees">
          <Input type="number" value={Number(form.employees ?? 0)} onChange={(e) => setForm({ employees: Number(e.target.value) })} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Market share (%)">
          <Input type="number" step={0.1} value={Number(form.market_share ?? 0)} onChange={(e) => setForm({ market_share: Number(e.target.value) })} />
        </Field>
        <Field label="Avg revenue / customer ($)" hint="Auto-computed from sales ÷ customers.">
          <Input type="number" disabled value={form.customers ? Math.round(Number(form.sales) / Math.max(1, Number(form.customers))) : 0} />
        </Field>
      </div>
      <div className="rounded-lg border border-muted bg-muted/40 p-3 text-[11px] leading-relaxed text-muted-foreground">
        <BarChart3 className="mb-1 h-3.5 w-3.5 inline-block text-primary" /> These inputs feed the health engine: revenue per customer, employee productivity and market positioning.
      </div>
    </div>
  );
}

function GrowthStep({ form, setForm }: { form: Record<string, unknown>; setForm: (p: Record<string, unknown>) => void }) {
  return (
    <div className="space-y-4">
      <StepTitle icon={TrendingUp} title="Growth ambitions & KPIs" subtitle="The parameters we use to assume your future growth." />
      <div className="grid grid-cols-2 gap-3">
        <Field label="YoY growth target (%)">
          <Input type="number" value={Number(form.growth_rate ?? 0)} onChange={(e) => setForm({ growth_rate: Number(e.target.value) })} />
        </Field>
        <Field label="Churn rate (%)">
          <Input type="number" step={0.1} value={Number(form.churn_rate ?? 0)} onChange={(e) => setForm({ churn_rate: Number(e.target.value) })} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Customer LTV ($)">
          <MoneyInput value={form.customer_lifetime_value} onChange={(v) => setForm({ customer_lifetime_value: v })} />
        </Field>
        <Field label="NPS score">
          <Input type="number" min={-100} max={100} value={Number(form.nps_score ?? 0)} onChange={(e) => setForm({ nps_score: Number(e.target.value) })} />
        </Field>
      </div>
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-[11px] leading-relaxed text-muted-foreground">
        <Sparkles className="mb-1 h-3.5 w-3.5 inline-block text-primary" /> Growth rate drives the 12-month revenue trajectory; churn & LTV tune customer-acquisition economics in simulations.
      </div>
    </div>
  );
}

function SupplyChainStep({ form, setForm }: { form: Record<string, unknown>; setForm: (p: Record<string, unknown>) => void }) {
  const suppliers = (form.suppliers as Array<Record<string, string>>) ?? [];
  const warehouses = (form.warehouses as Array<Record<string, string>>) ?? [];

  const setSupplier = (i: number, key: string, value: string) => {
    const next = suppliers.map((s, j) => (j === i ? { ...s, [key]: value } : s));
    setForm({ suppliers: next });
  };
  const setWarehouse = (i: number, key: string, value: string) => {
    const next = warehouses.map((w, j) => (j === i ? { ...w, [key]: value } : w));
    setForm({ warehouses: next });
  };

  return (
    <div className="space-y-4">
      <StepTitle icon={Truck} title="Supply chain (optional)" subtitle="Quick-start your network — you can add more later in Settings." />
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-muted-foreground">Suppliers</p>
          <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => setForm({ suppliers: [...suppliers, { name: "", location: "", country: "" }] })}>
            + Add
          </Button>
        </div>
        {suppliers.map((s, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
            <Input placeholder="Supplier name" value={s.name} onChange={(e) => setSupplier(i, "name", e.target.value)} />
            <Input placeholder="Location / country" value={s.location} onChange={(e) => setSupplier(i, "location", e.target.value)} />
            <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => setForm({ suppliers: suppliers.filter((_, j) => j !== i) })} aria-label="Remove supplier">
              ✕
            </Button>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-muted-foreground">Warehouses</p>
          <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => setForm({ warehouses: [...warehouses, { name: "", location: "" }] })}>
            + Add
          </Button>
        </div>
        {warehouses.map((w, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
            <Input placeholder="Warehouse name" value={w.name} onChange={(e) => setWarehouse(i, "name", e.target.value)} />
            <Input placeholder="Location" value={w.location} onChange={(e) => setWarehouse(i, "location", e.target.value)} />
            <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => setForm({ warehouses: warehouses.filter((_, j) => j !== i) })} aria-label="Remove warehouse">
              ✕
            </Button>
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-muted bg-muted/40 p-3 text-[11px] leading-relaxed text-muted-foreground">
        <Warehouse className="mb-1 h-3.5 w-3.5 inline-block text-primary" /> Skip for now — your twin works with business data alone. Add suppliers, inventory and shipments anytime.
      </div>
    </div>
  );
}

function StepTitle({ icon: Icon, title, subtitle }: { icon: typeof Building2; title: string; subtitle: string }) {
  return (
    <div className="mb-1 flex items-start gap-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="h-5 w-5" />
      </span>
      <div>
        <h2 className="text-base font-semibold leading-tight">{title}</h2>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </div>
    </div>
  );
}

/* ── Payload builder ───────────────────────────────────────────────────────── */

function buildSeedPayload(form: Record<string, unknown>) {
  const suppliers = ((form.suppliers as Array<Record<string, string>>) ?? [])
    .filter((s) => s.name?.trim())
    .map((s) => ({ name: s.name, location: s.location || "—", country: s.location || "—", lead_time_days: 7 }));
  const warehouses = ((form.warehouses as Array<Record<string, string>>) ?? [])
    .filter((w) => w.name?.trim())
    .map((w) => ({ name: w.name, location: w.location || "—", capacity: 10000 }));

  const business: Record<string, unknown> = {
    name: String(form.name).trim(),
    industry: String(form.industry ?? "general"),
    description: String(form.description ?? "") || undefined,
    revenue: Number(form.revenue ?? 0),
    expenses: Number(form.expenses ?? 0),
    profit: Number(form.revenue ?? 0) - Number(form.expenses ?? 0),
    cash_flow: Number(form.cash_flow ?? 0),
    customers: Number(form.customers ?? 0),
    employees: Number(form.employees ?? 0),
    sales: Number(form.sales ?? 0),
    marketing_budget: Number(form.marketing_budget ?? 0),
    market_share: Number(form.market_share ?? 0),
    kpis: {
      revenue_growth: Number(form.growth_rate ?? 0),
      churn_rate: Number(form.churn_rate ?? 0),
      customer_lifetime_value: Number(form.customer_lifetime_value ?? 0),
      nps_score: Number(form.nps_score ?? 0),
    },
  };

  return {
    business,
    supply_chain: {
      suppliers,
      warehouses,
    },
  };
}

function formatMoney(v: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(v);
}
