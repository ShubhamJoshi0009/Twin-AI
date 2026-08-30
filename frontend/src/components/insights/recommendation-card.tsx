"use client";

import { motion } from "framer-motion";
import { Lightbulb, Target, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Strategy } from "@/lib/types";
import { cn } from "@/lib/utils";

const PRIORITY_VARIANT: Record<string, "critical" | "warning" | "info"> = {
  high: "critical",
  medium: "warning",
  low: "info",
};

interface RecommendationCardProps {
  strategy: Strategy;
  index?: number;
}

/** A single AI-generated strategy recommendation. */
export function RecommendationCard({ strategy, index = 0 }: RecommendationCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.07 }}
    >
      <Card className="group h-full border-l-4 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
        style={{ borderLeftColor: strategy.priority === "high" ? "hsl(var(--destructive))" : strategy.priority === "medium" ? "hsl(var(--warning))" : "hsl(var(--chart-1))" }}
      >
        <CardHeader className="flex-row items-start justify-between space-y-0 pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
              {strategy.strategy_type === "growth" ? <TrendingUp className="h-3.5 w-3.5" /> : strategy.strategy_type === "efficiency" ? <Target className="h-3.5 w-3.5" /> : <Lightbulb className="h-3.5 w-3.5" />}
            </span>
            {strategy.title}
          </CardTitle>
          <Badge variant={PRIORITY_VARIANT[strategy.priority] ?? "info"} className="capitalize">
            {strategy.priority}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm text-muted-foreground">{strategy.description}</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(strategy.expected_impact ?? {}).map(([k, v]) => (
              <span key={k} className={cn("rounded-md bg-muted px-2 py-0.5 text-xs font-medium tabular-nums")}>
                {k.replaceAll("_", " ")}: {String(v)}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
