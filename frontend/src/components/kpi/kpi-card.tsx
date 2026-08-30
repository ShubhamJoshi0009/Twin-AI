"use client";

import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Sparkline } from "@/components/charts/sparkline";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface KPICardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  delta?: number | null;
  deltaLabel?: string;
  spark?: number[];
  sparkColor?: string;
  description?: string;
  index?: number;
  className?: string;
}

/** Executive KPI card: label, animated value, delta indicator and optional sparkline. */
export function KPICard({
  label,
  value,
  icon: Icon,
  delta,
  deltaLabel,
  spark,
  sparkColor,
  description,
  index = 0,
  className,
}: KPICardProps) {
  const positive = delta !== null && delta !== undefined && delta > 0;
  const negative = delta !== null && delta !== undefined && delta < 0;
  const neutral = delta === 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06, ease: "easeOut" }}
    >
      <Card className={cn("group relative overflow-hidden p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg", className)}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-110">
              <Icon className="h-4 w-4" />
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="cursor-help text-sm font-medium">{label}</span>
              </TooltipTrigger>
              {description && <TooltipContent>{description}</TooltipContent>}
            </Tooltip>
          </div>
          {delta !== null && delta !== undefined && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums",
                positive && "bg-success/10 text-success",
                negative && "bg-destructive/10 text-destructive",
                neutral && "bg-muted text-muted-foreground"
              )}
            >
              {positive ? <ArrowUpRight className="h-3 w-3" /> : negative ? <ArrowDownRight className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
              {delta !== null && delta !== undefined ? `${Math.abs(delta).toFixed(1)}%` : "—"}
            </span>
          )}
        </div>

        <div className="mt-3 flex items-end justify-between gap-3">
          <div>
            <div className="text-2xl font-bold tabular-nums tracking-tight">{value}</div>
            {deltaLabel && <div className="mt-0.5 text-xs text-muted-foreground">{deltaLabel}</div>}
          </div>
          {spark && spark.length > 1 && (
            <div className="w-24 opacity-80 transition-opacity group-hover:opacity-100">
              <Sparkline data={spark} color={sparkColor} height={36} />
            </div>
          )}
        </div>
      </Card>
    </motion.div>
  );
}
