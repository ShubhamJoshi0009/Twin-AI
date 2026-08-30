import { SEVERITY_THEME } from "@/lib/constants";
import type { Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
}

/** Pill badge colored by severity (critical / high / medium / low / info). */
export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const theme = SEVERITY_THEME[severity] ?? SEVERITY_THEME.info;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        theme.bg,
        theme.border,
        theme.text,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", theme.dot)} />
      {theme.label}
    </span>
  );
}
