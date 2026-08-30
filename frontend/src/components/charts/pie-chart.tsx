"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { colorAt } from "@/components/charts/chart-utils";
import { useMounted } from "@/hooks/use-mounted";
import { formatNumber } from "@/lib/utils";

interface PieDatum {
  name: string;
  value: number;
  color?: string;
}

interface PieChartProps {
  data: PieDatum[];
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
  centerLabel?: string;
  centerValue?: string;
}

/** Pie / donut chart with hover tooltips and a configurable center label. */
export function PieChartComponent({
  data,
  height = 240,
  innerRadius = 55,
  outerRadius = 82,
  centerLabel,
  centerValue,
}: PieChartProps) {
  const mounted = useMounted();
  if (!mounted) return <div style={{ height, width: "100%" }} aria-hidden />;

  return (
    <div className="relative" style={{ height, width: "100%" }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Tooltip content={<ChartTooltip formatter={(v) => formatNumber(v)} />} />
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={3}
            strokeWidth={2}
            stroke="hsl(var(--card))"
          >
            {data.map((d, i) => (
              <Cell key={d.name} fill={d.color ?? colorAt(i)} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      {(centerLabel || centerValue) && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold tabular-nums">{centerValue}</span>
          <span className="text-xs text-muted-foreground">{centerLabel}</span>
        </div>
      )}
    </div>
  );
}
