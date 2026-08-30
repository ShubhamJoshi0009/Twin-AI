"use client";

import { formatCurrency, formatNumber } from "@/lib/utils";

interface TooltipEntry {
  name?: string;
  value?: number | string;
  color?: string;
  payload?: Record<string, unknown>;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  formatter?: (value: number, name: string) => string;
}

/** Shared tooltip used by all charts (hover tooltips). */
export function ChartTooltip({ active, payload, label, formatter }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover/95 px-3 py-2 text-xs shadow-lg backdrop-blur">
      {label && <p className="mb-1.5 font-semibold text-popover-foreground">{label}</p>}
      <div className="space-y-1">
        {payload.map((entry, i) => (
          <div key={i} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span className="h-2 w-2 rounded-full" style={{ background: entry.color }} />
              {entry.name}
            </span>
            <span className="font-medium tabular-nums text-popover-foreground">
              {formatter && typeof entry.value === "number"
                ? formatter(entry.value, entry.name ?? "")
                : formatNumber(typeof entry.value === "number" ? entry.value : NaN)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Currency formatter for chart tooltips. */
export function money(value: number) {
  return formatCurrency(value, { compact: true });
}

/** Number formatter for chart tooltips. */
export function plain(value: number) {
  return formatNumber(value);
}
