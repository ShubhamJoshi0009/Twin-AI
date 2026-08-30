"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  CheckCircle2,
  Database,
  Download,
  FileJson,
  HardDrive,
  Loader2,
  RotateCcw,
  Upload,
  X,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
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
import { errorMessage } from "@/lib/api/client";
import {
  applySeedData,
  getSeedStatus,
  getSeedTemplate,
  type SeedCounts,
  type SeedStatus,
  type SeedSummary,
} from "@/lib/api/system";
import { cn } from "@/lib/utils";

interface ParsedCounts {
  simulations: number;
  suppliers: number;
  warehouses: number;
  inventory: number;
  shipments: number;
}

interface ParsedSeedFile {
  businessName: string;
  counts: ParsedCounts;
  /** The full raw JSON payload — what actually gets sent to the backend. */
  raw: unknown;
}

const PARSED_COUNT_LABELS: Array<{ key: keyof ParsedCounts; label: string }> = [
  { key: "suppliers", label: "Suppliers" },
  { key: "warehouses", label: "Warehouses" },
  { key: "inventory", label: "Inventory" },
  { key: "shipments", label: "Shipments" },
  { key: "simulations", label: "Simulations" },
];

const RESULT_COUNT_LABELS: Array<{ key: keyof SeedCounts; label: string }> = [
  { key: "suppliers", label: "Suppliers" },
  { key: "warehouses", label: "Warehouses" },
  { key: "inventory", label: "Inventory" },
  { key: "shipments", label: "Shipments" },
  { key: "simulations", label: "Simulations" },
  { key: "insights", label: "Insights" },
];

/** Client-side validation of a seed file before it is sent to the backend. */
function parseSeedFile(text: string): ParsedSeedFile | { error: string } {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { error: "The file is not valid JSON." };
  }
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return { error: "The JSON must be an object with a \"business\" section." };
  }
  const obj = raw as Record<string, unknown>;
  const business =
    obj.business && typeof obj.business === "object" && !Array.isArray(obj.business)
      ? (obj.business as Record<string, unknown>)
      : obj;
  if (typeof business.name !== "string" || !business.name.trim()) {
    return { error: "Missing \"business.name\" — this does not look like a seed file." };
  }
  const sc =
    obj.supply_chain && typeof obj.supply_chain === "object" && !Array.isArray(obj.supply_chain)
      ? (obj.supply_chain as Record<string, unknown>)
      : {};
  const arr = (v: unknown) => (Array.isArray(v) ? v.length : 0);
  return {
    businessName: business.name.trim(),
    counts: {
      simulations: arr(obj.simulations),
      suppliers: arr(sc.suppliers),
      warehouses: arr(sc.warehouses),
      inventory: arr(sc.inventory),
      shipments: arr(sc.shipments),
    },
    raw: obj,
  };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DataSeeder() {
  const [status, setStatus] = useState<SeedStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [parsed, setParsed] = useState<ParsedSeedFile | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState(0);
  const [parseError, setParseError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<SeedSummary | null>(null);
  const [confirmAction, setConfirmAction] = useState<{ data: unknown | null; label: string } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const refreshStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      setStatus(await getSeedStatus());
    } catch {
      // Backend unreachable — leave status null; the UI shows an offline hint.
      setStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  const handleFile = useCallback((file: File) => {
    setParseError(null);
    setResult(null);
    const reader = new FileReader();
    reader.onload = () => {
      const res = parseSeedFile(String(reader.result ?? ""));
      if ("error" in res) {
        setParsed(null);
        setFileName(null);
        setFileSize(0);
        setParseError(res.error);
        return;
      }
      setParsed(res);
      setFileName(file.name);
      setFileSize(file.size);
    };
    reader.onerror = () => {
      setParsed(null);
      setFileName(null);
      setFileSize(0);
      setParseError("Could not read the selected file.");
    };
    reader.readAsText(file);
  }, []);

  const clearFile = useCallback(() => {
    setParsed(null);
    setFileName(null);
    setFileSize(0);
    setParseError(null);
    if (inputRef.current) inputRef.current.value = "";
  }, []);

  const runApply = useCallback(
    async (data: unknown | null) => {
      setApplying(true);
      setParseError(null);
      setResult(null);
      try {
        // Replaces existing data when the DB already has a dataset; otherwise
        // a plain (non-destructive) seed is enough.
        const summary = await applySeedData(data, Boolean(status?.has_data));
        setResult(summary);
        if (summary.skipped) {
          // Nothing changed — keep the file so the user can retry.
          toast.info(summary.reason ?? "No changes were made.");
        } else {
          toast.success(
            summary.twin ? `“${summary.twin.name}” is now the live dataset` : "Dataset applied successfully"
          );
          clearFile();
        }
        await refreshStatus();
      } catch (err) {
        const msg = errorMessage(err);
        setParseError(msg);
        toast.error(msg);
      } finally {
        setApplying(false);
      }
    },
    [status?.has_data, refreshStatus, clearFile]
  );

  /** Ask for confirmation before replacing existing data, then apply. */
  const requestApply = useCallback(
    (data: unknown | null, label: string) => {
      if (status?.has_data) {
        setConfirmAction({ data, label });
      } else {
        runApply(data);
      }
    },
    [status?.has_data, runApply]
  );

  const handleDownloadTemplate = useCallback(async () => {
    try {
      const tpl = await getSeedTemplate();
      const blob = new Blob([JSON.stringify(tpl, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "my-business.json";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Template downloaded — fill it in and re-upload it here");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }, []);

  const offline = !statusLoading && status === null;
  const hasFile = parsed !== null && fileName !== null;
  const parsedCounts = parsed?.counts;
  const resultCounts = result?.counts;
  const countChips = parsedCounts ? PARSED_COUNT_LABELS.filter(({ key }) => parsedCounts[key] > 0) : [];
  const resultChips = resultCounts ? RESULT_COUNT_LABELS.filter(({ key }) => resultCounts[key] > 0) : [];

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Database className="h-4 w-4 text-primary" />
          Data &amp; Seeding
        </CardTitle>
        <CardDescription className="text-xs">
          Upload your own business &amp; supply chain profile as JSON, or restore the built-in demo dataset.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Database status */}
        <div className="flex items-center justify-between rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-2">
            <HardDrive className="h-3.5 w-3.5" />
            {statusLoading ? (
              "Checking database…"
            ) : offline ? (
              "Backend unreachable — start the API server to apply data"
            ) : status?.has_data ? (
              <>
                Database contains <span className="font-semibold text-foreground">{status.twin_count}</span>{" "}
                {status.twin_count === 1 ? "digital twin" : "digital twins"}
              </>
            ) : (
              "Database is empty — ready for first seed"
            )}
          </span>
          {!offline && (
            <button onClick={refreshStatus} className="text-muted-foreground transition-colors hover:text-foreground" aria-label="Refresh status">
              <RotateCcw className={cn("h-3.5 w-3.5", statusLoading && "animate-spin")} />
            </button>
          )}
        </div>

        <Separator />

        {/* Dropzone / file summary */}
        {!hasFile ? (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const file = e.dataTransfer.files?.[0];
              if (file) handleFile(file);
            }}
            className={cn(
              "flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-8 text-center transition-all",
              dragOver
                ? "border-primary bg-primary/5 scale-[1.01]"
                : "border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50"
            )}
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Upload className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-medium">Drop your seed file here or click to browse</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                JSON with a <span className="font-mono">business</span> section (see template below for the full format)
              </p>
            </div>
          </button>
        ) : (
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-3 rounded-lg border bg-muted/30 px-3 py-2.5">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <FileJson className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {fileName} <span className="text-xs font-normal text-muted-foreground">· {formatBytes(fileSize)}</span>
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    Business: <span className="font-medium text-foreground">{parsed?.businessName}</span>
                  </p>
                </div>
              </div>
              <button
                onClick={clearFile}
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                aria-label="Remove file"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {countChips.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {countChips.map(({ key, label }) => (
                  <span key={key} className="rounded-full border bg-background px-2.5 py-0.5 text-xs text-muted-foreground">
                    {parsedCounts?.[key]} {label}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            onClick={() => hasFile && fileName && parsed && requestApply(parsed.raw, `“${fileName}”`)}
            disabled={!hasFile || applying || offline}
          >
            {applying ? <Loader2 className="animate-spin" /> : <Upload />}
            Apply to database
          </Button>
          <Button size="sm" variant="outline" onClick={() => requestApply(null, "the demo dataset")} disabled={applying || offline}>
            <RotateCcw /> Restore demo data
          </Button>
          <Button size="sm" variant="ghost" onClick={handleDownloadTemplate} disabled={applying || offline}>
            <Download /> Download template
          </Button>
        </div>

        {/* Inline error */}
        {parseError && (
          <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {parseError}
          </p>
        )}

        {/* Success summary */}
        {result && !result.skipped && (
          <div className="space-y-2 rounded-lg border border-success/30 bg-success/5 px-3 py-3">
            <p className="flex items-center gap-2 text-sm font-medium text-success">
              <CheckCircle2 className="h-4 w-4" />
              {result.twin ? `Seeded “${result.twin.name}”` : "Dataset applied"}
            </p>
            {resultChips.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {resultChips.map(({ key, label }) => (
                  <span key={key} className="rounded-full border border-success/30 bg-background px-2.5 py-0.5 text-xs text-muted-foreground">
                    {resultCounts?.[key]} {label}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>

      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      {/* Replace-existing confirmation */}
      <AlertDialog open={confirmAction !== null} onOpenChange={(open) => !open && setConfirmAction(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Replace existing data?</AlertDialogTitle>
            <AlertDialogDescription>
              The database already contains data. Seeding with {confirmAction?.label} will replace all digital
              twins, simulations, insights and supply chain records. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={applying}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                if (confirmAction) runApply(confirmAction.data);
                setConfirmAction(null);
              }}
              disabled={applying}
            >
              {applying ? <Loader2 className="animate-spin" /> : null}
              Replace data
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
