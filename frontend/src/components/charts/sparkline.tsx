"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { colorAt } from "@/components/charts/chart-utils";
import { useMounted } from "@/hooks/use-mounted";

interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
}

/** Compact area sparkline used inside KPI cards. */
export function Sparkline({ data, color, height = 40 }: SparklineProps) {
  const mounted = useMounted();
  if (!mounted) return <div style={{ height, width: "100%" }} aria-hidden />;

  const series = data.map((value, i) => ({ i, value }));
  const stroke = color ?? colorAt(0);
  return (
    <div style={{ height, width: "100%" }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <defs>
            <linearGradient id={`spark-${color ?? "d"}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.25} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={stroke}
            strokeWidth={1.8}
            fill={`url(#spark-${color ?? "d"})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
