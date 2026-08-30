"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  Boxes,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  Download,
  FileCode,
  FileJson,
  FileSpreadsheet,
  FileText,
  FileType,
  ListChecks,
  Radio,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";
import { useSourceChecklist } from "@/hooks/use-api";
import * as business from "@/lib/api/business";
import type { ReportExportFormat } from "@/lib/api/business";
import { errorMessage } from "@/lib/api/client";
import { isDemoTwinId } from "@/lib/mock/mock-data";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RelativeTime } from "@/components/shared/relative-time";
import { SkeletonGrid } from "@/components/shared/state-views";
import type { SourceCategory, SourceChecklistItem, SourceStatus } from "@/lib/types";

const CATEGORY_ICONS: Record<SourceCategory, typeof FileText> = {
  "user-provided": FileText,
  financial: CircleDollarSign,
  operational: Boxes,
  market: TrendingUp,
  "ai-generated": Sparkles,
  "real-time": Radio,
};

const CATEGORY_COLORS: Record<SourceCategory, string> = {
  "user-provided": "text-chart-1 bg-chart-1/10 border-chart-1/20",
  financial: "text-chart-2 bg-chart-2/10 border-chart-2/20",
  operational: "text-chart-3 bg-chart-3/10 border-chart-3/20",
  market: "text-chart-4 bg-chart-4/10 border-chart-4/20",
  "ai-generated": "text-chart-5 bg-chart-5/10 border-chart-5/20",
  "real-time": "text-primary bg-primary/10 border-primary/20",
};

const STATUS_VARIANT: Record<SourceStatus, "success" | "secondary" | "warning" | "destructive"> = {
  verified: "success",
  complete: "secondary",
  partial: "warning",
  missing: "destructive",
};

const STATUS_BAR: Record<SourceStatus, string> = {
  verified: "bg-success",
  complete: "bg-primary",
  partial: "bg-warning",
  missing: "bg-destructive",
};

const STATUS_ORDER: SourceStatus[] = ["verified", "complete", "partial", "missing"];

/** Highlight query matches in text (single first match per field, case-insensitive). */
function Highlight({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.trim().toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded-sm bg-primary/25 px-0.5 font-semibold text-primary">{text.slice(idx, idx + query.trim().length)}</mark>
      {text.slice(idx + query.trim().length)}
    </>
  );
}

/** True when a section has missing data (incomplete coverage or a missing check). */
function hasMissingData(item: SourceChecklistItem): boolean {
  return item.coverage_score < 100 || item.checks.some((c) => !c.present);
}

function CoverageRing({ value, size = 64 }: { value: number; size?: number }) {
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const filled = Math.max(0, Math.min(100, value)) / 100;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="hsl(var(--muted))" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - filled) }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-sm font-bold tabular-nums leading-none">{Math.round(value)}</span>
        <span className="text-[8px] uppercase tracking-wide text-muted-foreground">cover</span>
      </div>
    </div>
  );
}

interface SourceRowProps {
  item: SourceChecklistItem;
  query: string;
  completed: boolean;
  saving: boolean;
  onToggleComplete: (sourceId: string) => void;
  defaultOpen?: boolean;
}

function SourceRow({ item, query, completed, saving, onToggleComplete, defaultOpen }: SourceRowProps) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const Icon = CATEGORY_ICONS[item.category] ?? ListChecks;
  const color = CATEGORY_COLORS[item.category] ?? CATEGORY_COLORS["user-provided"];
  const present = item.checks.filter((c) => c.present).length;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`overflow-hidden rounded-xl border bg-card transition-colors hover:border-border/80 ${completed ? "border-success/30" : ""}`}
    >
      <div className="flex w-full items-center gap-3 px-4 py-3">
        {/* Completion toggle */}
        <Checkbox
          checked={completed}
          disabled={saving}
          onCheckedChange={() => onToggleComplete(item.source_id)}
          aria-label={`Mark ${item.name} complete`}
          className={completed ? "border-success bg-success text-white" : ""}
        />
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${color}`}>
            <Icon className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold"><Highlight text={item.name} query={query} /></p>
              <Badge variant={STATUS_VARIANT[item.status]} className="text-[10px] capitalize">
                {item.status}
              </Badge>
              {completed && (
                <span className="flex items-center gap-0.5 text-[10px] text-success">
                  <CheckCircle2 className="h-3 w-3" /> complete
                </span>
              )}
            </div>
            <p className="truncate text-xs text-muted-foreground"><Highlight text={item.notes} query={query} /></p>
            <p className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
              <span className="capitalize">{item.category}</span>
              <span className="h-0.5 w-0.5 rounded-full bg-muted-foreground/40" />
              <span>{item.owner}</span>
            </p>
          </div>
        </button>
        <div className="hidden w-24 shrink-0 sm:block">
          <div className="mb-1 flex justify-between text-[10px] text-muted-foreground">
            <span>{present}/{item.checks.length}</span>
            <span className="tabular-nums font-semibold">{Math.round(item.coverage_score)}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <motion.div
              className={`h-full rounded-full ${STATUS_BAR[item.status]}`}
              initial={{ width: 0 }}
              animate={{ width: `${item.coverage_score}%` }}
              transition={{ duration: 0.6, delay: 0.1 }}
            />
          </div>
        </div>
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="space-y-1.5 border-t px-4 py-3">
              {item.checks.map((c) => (
                <div key={c.field} className="flex items-start gap-2 text-xs">
                  {c.present ? (
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-success/15 text-success">
                      <Check className="h-3 w-3" />
                    </span>
                  ) : (
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                      <X className="h-3 w-3" />
                    </span>
                  )}
                  <span className="w-36 shrink-0 font-medium text-muted-foreground"><Highlight text={c.label} query={query} /></span>
                  <span className={c.present ? "truncate font-medium" : "italic text-muted-foreground"}>
                    {c.present ? <Highlight text={c.value} query={query} /> : "not provided"}
                  </span>
                </div>
              ))}
              {item.last_updated && (
                <p className="flex items-center gap-1 pt-1 text-[10px] text-muted-foreground/70">
                  <span className="h-1 w-1 rounded-full bg-muted-foreground/40" /> Last updated <RelativeTime value={item.last_updated} />
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function SourceChecklist({ twinId }: { twinId: string | null }) {
  const { data, isLoading, refetch, isFetching } = useSourceChecklist(twinId);
  const [openAll, setOpenAll] = useState(false);

  // Search + filter state
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [owner, setOwner] = useState<string>("all");
  const [missingOnly, setMissingOnly] = useState(false);

  // Saved completion state (synced from server, mutated optimistically)
  const [completions, setCompletions] = useState<Record<string, boolean>>({});
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const items = useMemo(() => data?.items ?? [], [data]);
  const owners = useMemo(() => Array.from(new Set(items.map((i) => i.owner).filter(Boolean))).sort(), [items]);

  useEffect(() => {
    if (data) {
      setCompletions(Object.fromEntries(data.items.map((i) => [i.source_id, i.completed])));
      setSavedAt(data.saved_at ?? null);
    }
  }, [data]);

  // Live completion count — reflects optimistic toggles before the next refetch.
  const completedCount = useMemo(
    () => items.reduce((n, i) => n + (completions[i.source_id] ? 1 : 0), 0),
    [items, completions]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
      if (category !== "all" && item.category !== category) return false;
      if (status !== "all" && item.status !== status) return false;
      if (owner !== "all" && item.owner !== owner) return false;
      if (missingOnly && !hasMissingData(item)) return false;
      if (q) {
        const haystack = [
          item.name,
          item.notes,
          item.owner,
          item.category,
          item.status,
          ...item.checks.flatMap((c) => [c.label, c.value]),
        ]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [items, query, category, status, owner, missingOnly]);

  const hasActiveFilters = query.trim() !== "" || category !== "all" || status !== "all" || owner !== "all" || missingOnly;

  const resetFilters = () => {
    setQuery("");
    setCategory("all");
    setStatus("all");
    setOwner("all");
    setMissingOnly(false);
  };

  const realId = twinId && !isDemoTwinId(twinId) ? twinId : null;

  const toggleComplete = async (sourceId: string) => {
    if (!realId) {
      toast.error("Connect to the backend to save checklist state.");
      return;
    }
    const next = { ...completions, [sourceId]: !completions[sourceId] };
    setCompletions(next);
    setSaving(true);
    try {
      const updated = await business.saveSourceChecklist(realId, next);
      setCompletions(Object.fromEntries(updated.items.map((i) => [i.source_id, i.completed])));
      setSavedAt(updated.saved_at ?? null);
      toast.success("Checklist saved");
    } catch (err) {
      setCompletions(Object.fromEntries(items.map((i) => [i.source_id, i.completed])));
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const EXT: Record<ReportExportFormat, string> = {
    pdf: "pdf",
    html: "html",
    csv: "csv",
    markdown: "md",
    json: "json",
  };

  const handleExport = async (format: ReportExportFormat) => {
    if (!realId) {
      toast.error("Connect to the backend to export the report.");
      return;
    }
    try {
      const blob = await business.exportSourceChecklist(realId, format);
      // Blob-typed error responses (4xx/5xx) arrive as JSON blobs because the
      // request uses `responseType: blob`. Surface the real message instead of
      // silently failing or downloading a broken file.
      if (blob.type.includes("application/json")) {
        let message = "Export failed";
        try {
          message = (JSON.parse(await blob.text()) as { detail?: string })?.detail ?? message;
        } catch {
          /* non-JSON error payload — keep the default message */
        }
        throw new Error(message);
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(data?.company ?? "profile").toLowerCase().replaceAll(" ", "-")}-profile-report.${EXT[format]}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Revoke asynchronously: revoking the object URL synchronously right
      // after click() can abort the download in real browsers (Chromium race).
      window.setTimeout(() => URL.revokeObjectURL(url), 2000);
      toast.success(`Report exported (${format.toUpperCase()})`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const totals = useMemo(() => {
    const t = { verified: 0, complete: 0, partial: 0, missing: 0 };
    items.forEach((i) => { t[i.status] += 1; });
    return t;
  }, [items]);

  return (
    <Card id="source-checklist" className="scroll-mt-28">
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2 text-sm">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ListChecks className="h-4 w-4" />
            </span>
            Data Source Checklist
          </CardTitle>
          <CardDescription className="mt-1 text-xs">
            {data?.company ? `Provenance audit for ${data.company} — ${data.industry}` : "Provenance audit of every source behind this profile"}
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpenAll((o) => !o)} className="hidden sm:inline-flex">
            {openAll ? "Collapse all" : "Expand all"}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Download className="h-3.5 w-3.5" /> Export report <ChevronDown className="h-3 w-3 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Profile report
              </DropdownMenuLabel>
              <DropdownMenuItem onClick={() => handleExport("pdf")}>
                <FileText className="h-4 w-4 text-destructive" /> PDF document
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("html")}>
                <FileCode className="h-4 w-4 text-chart-1" /> HTML page
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("csv")}>
                <FileSpreadsheet className="h-4 w-4 text-chart-2" /> CSV checklist
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => handleExport("markdown")}>
                <FileType className="h-4 w-4 text-chart-4" /> Markdown
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("json")}>
                <FileJson className="h-4 w-4 text-chart-3" /> JSON data
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Summary strip */}
        <div className="flex flex-wrap items-center gap-4 rounded-xl border bg-muted/30 p-4">
          <CoverageRing value={data?.overall_coverage ?? 0} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">Profile coverage</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {data?.overall_coverage !== undefined && data.overall_coverage >= 70
                ? "Strongly sourced profile — most data domains are populated."
                : data?.overall_coverage !== undefined && data.overall_coverage >= 40
                  ? "Partially sourced — several domains still need data."
                  : "Thinly sourced — add data to unlock reliable simulations."}
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="text-[10px]">
                {completedCount}/{data?.total_sections ?? items.length} sections complete
              </Badge>
              {savedAt && (
                <Badge variant="outline" className="gap-1 text-[10px] text-success">
                  <Save className="h-3 w-3" /> Saved <RelativeTime value={savedAt} />
                </Badge>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Badge variant="success" className="text-[10px]">{totals.verified} verified</Badge>
            <Badge variant="secondary" className="text-[10px]">{totals.complete} complete</Badge>
            <Badge variant="warning" className="text-[10px]">{totals.partial} partial</Badge>
            <Badge variant="destructive" className="text-[10px]">{totals.missing} missing</Badge>
          </div>
        </div>

        {/* Search + filters toolbar */}
        <div className="space-y-2 rounded-xl border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[200px] flex-1">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search sections, owners, values…"
                className="pl-8"
                aria-label="Search source checklist"
              />
            </div>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-[160px]" aria-label="Filter by section">
                <SelectValue placeholder="Section" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All sections</SelectItem>
                {Object.keys(CATEGORY_ICONS).map((c) => (
                  <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={owner} onValueChange={setOwner}>
              <SelectTrigger className="w-[170px]" aria-label="Filter by owner">
                <SelectValue placeholder="Owner / agent" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All owners</SelectItem>
                {owners.map((o) => (
                  <SelectItem key={o} value={o}>{o}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={resetFilters} aria-label="Reset filters">
                <RotateCcw className="h-3.5 w-3.5" /> Reset
              </Button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-[10px] uppercase tracking-wide text-muted-foreground/70">Status</span>
            <button
              type="button"
              onClick={() => setMissingOnly((m) => !m)}
              className={`rounded-full border px-2.5 py-0.5 text-[10px] transition-colors ${missingOnly ? "border-destructive/50 bg-destructive/10 text-destructive" : "border-border text-muted-foreground hover:bg-accent"}`}
              aria-pressed={missingOnly}
            >
              ⚠ Missing data only
            </button>
            {STATUS_ORDER.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setStatus((cur) => (cur === s ? "all" : s))}
                className={`rounded-full border px-2.5 py-0.5 text-[10px] capitalize transition-colors ${
                  status === s ? "border-primary/50 bg-primary/10 text-primary" : "border-border text-muted-foreground hover:bg-accent"
                }`}
                aria-pressed={status === s}
              >
                {s}
              </button>
            ))}
            {hasActiveFilters && (
              <span className="ml-auto text-[10px] text-muted-foreground">
                {filtered.length} of {items.length} sections
              </span>
            )}
          </div>
        </div>

        {isLoading ? (
          <SkeletonGrid count={4} />
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-10 text-center">
            <ListChecks className="h-8 w-8 text-muted-foreground/50" />
            <p className="text-sm font-medium">No source data available</p>
            <p className="text-xs text-muted-foreground">Create or update the business profile to generate its source checklist.</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-10 text-center">
            <Search className="h-8 w-8 text-muted-foreground/50" />
            <p className="text-sm font-medium">No sections match your filters</p>
            <Button variant="ghost" size="sm" onClick={resetFilters}>
              <RotateCcw className="h-3.5 w-3.5" /> Reset search & filters
            </Button>
          </div>
        ) : (
          <div className="grid gap-2 lg:grid-cols-2">
            {filtered.map((item, i) => (
              <SourceRow
                key={item.source_id}
                item={item}
                query={query}
                completed={completions[item.source_id] ?? false}
                saving={saving}
                onToggleComplete={toggleComplete}
                defaultOpen={openAll || (i === 0 && hasActiveFilters)}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
