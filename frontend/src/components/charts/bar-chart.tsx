"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell, Legend } from "recharts";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { colorAt } from "@/components/charts/chart-utils";
import { useMounted } from "@/hooks/use-mounted";

interface BarSeriesConfig {
  key: string;
  name: string;
  color?: string;
}

interface BarChartProps {
  data: Array<Record<string, unknown>>;
  xKey: string;
  series: BarSeriesConfig[];
  height?: number;
  formatter?: (value: number, name: string) => string;
  stacked?: boolean;
  rounded?: boolean;
  horizontal?: boolean;
  singleColor?: boolean;
}

/** Bar chart with hover tooltips and responsive layout. */
export function BarChartComponent({
  data,
  xKey,
  series,
  height = 260,
  formatter,
  stacked = false,
  rounded = true,
  horizontal = false,
  singleColor = false,
}: BarChartProps) {
  const mounted = useMounted();
  if (!mounted) return <div style={{ height, width: "100%" }} aria-hidden />;

  const radius: [number, number, number, number] = rounded ? [6, 6, 0, 0] : [0, 0, 0, 0];
  return (
    <div style={{ height, width: "100%" }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} layout={horizontal ? "vertical" : "horizontal"}>
          {!horizontal && <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />}
          {horizontal ? (
            <XAxis type="number" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
          ) : (
            <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} dy={6} />
          )}
          {horizontal ? (
            <YAxis
              dataKey={xKey}
              type="category"
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
              width={110}
            />
          ) : (
            <YAxis
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))}
            />
          )}
          <Tooltip content={<ChartTooltip formatter={formatter} />} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" iconSize={8} />}
          {series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={s.color ?? colorAt(i)}
              stackId={stacked ? "stack" : undefined}
              radius={stacked ? undefined : radius}
              maxBarSize={singleColor ? 48 : 40}
            >
              {singleColor &&
                data.map((entry, j) => <Cell key={j} fill={s.color ?? colorAt(j)} />)}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
