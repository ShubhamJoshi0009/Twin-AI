import { Badge, type BadgeProps } from "@/components/ui/badge";
import { SEVERITY_THEME } from "@/lib/constants";

const STATUS_VARIANT: Record<string, BadgeProps["variant"]> = {
  // generic
  active: "success",
  resolved: "muted",
  delivered: "success",
  completed: "success",
  healthy: "success",
  // in-progress states
  in_transit: "info",
  pending: "warning",
  processing: "info",
  scheduled: "info",
  // problem states
  delayed: "destructive",
  critical: "critical",
  low_stock: "warning",
  overstock: "info",
  out_of_stock: "critical",
  // risk
  high: "critical",
  medium: "warning",
  low: "info",
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

/** Renders a colored badge for a status string, with a severity dot. */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const key = status?.toLowerCase() ?? "";
  const variant = STATUS_VARIANT[key] ?? "secondary";
  const theme = SEVERITY_THEME[key as keyof typeof SEVERITY_THEME];
  return (
    <Badge variant={variant} className={className}>
      {theme && <span className={cn_dot(theme.dot)} />}
      <span className="capitalize">{status?.replaceAll("_", " ") ?? "—"}</span>
    </Badge>
  );
}

function cn_dot(color: string) {
  return `h-1.5 w-1.5 rounded-full ${color}`;
}
