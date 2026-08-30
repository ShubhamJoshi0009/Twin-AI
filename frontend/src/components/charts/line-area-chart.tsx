"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Brush,
} from "recharts";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { colorAt, withAlpha } from "@/components/charts/chart-utils";
import { useMounted } from "@/hooks/use-mounted";

export interface SeriesConfig {
  key: string;
  name: string;
  color?: string;
  area?: boolean;
}

interface LineAreaChartProps {
  data: Array<Record<string, unknown>>;
  xKey: string;
  series: SeriesConfig[];
  height?: number;
  formatter?: (value: number, name: string) => string;
  zoom?: boolean;
  grid?: boolean;
  type?: "line" | "area";
}

/** Line or area chart. Supports hover tooltips, zoom (brush) and responsive layout. */
export function LineAreaChart({
  data,
  xKey,
  series,
  height = 260,
  formatter,
  zoom = false,
  grid = true,
  type = "line",
}: LineAreaChartProps) {
  const mounted = useMounted();
  if (!mounted) return <div style={{ height, width: "100%" }} aria-hidden />;

  return (
    <div style={{ height, width: "100%" }}>
      <ResponsiveContainer width="100%" height="100%">
        {type === "area" ? (
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            {grid && <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />}
            <XAxis
              dataKey={xKey}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
              dy={6}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))}
            />
            <Tooltip content={<ChartTooltip formatter={formatter} />} cursor={{ stroke: "hsl(var(--border))" }} />
            {series.map((s, i) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color ?? colorAt(i)}
                fill={withAlpha(s.color ?? colorAt(i), 0.18)}
                strokeWidth={2}
                activeDot={{ r: 4, strokeWidth: 0 }}
              />
            ))}
            {zoom && <Brush dataKey={xKey} height={22} stroke="hsl(var(--muted-foreground))" travellerWidth={8} />}
          </AreaChart>
        ) : (
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            {grid && <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />}
            <XAxis
              dataKey={xKey}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
              dy={6}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))}
            />
            <Tooltip content={<ChartTooltip formatter={formatter} />} cursor={{ stroke: "hsl(var(--border))" }} />
            {series.map((s, i) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color ?? colorAt(i)}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
              />
            ))}
            {zoom && <Brush dataKey={xKey} height={22} stroke="hsl(var(--muted-foreground))" travellerWidth={8} />}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
