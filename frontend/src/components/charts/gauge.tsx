"use client";

import { motion } from "framer-motion";
import { HEALTH_COLORS } from "@/lib/constants";
import { useMounted } from "@/hooks/use-mounted";
import { cn } from "@/lib/utils";

interface GaugeProps {
  value: number; // 0-100
  label?: string;
  sublabel?: string;
  size?: number;
  className?: string;
}

function colorFor(value: number) {
  if (value >= 70) return HEALTH_COLORS.good;
  if (value >= 50) return HEALTH_COLORS.warning;
  return HEALTH_COLORS.critical;
}

/** Semi-circular gauge used for business health, supply chain health and confidence. */
export function Gauge({ value, label, sublabel, size = 180, className }: GaugeProps) {
  const mounted = useMounted();
  const clamped = Math.min(100, Math.max(0, value));
  const strokeWidth = 14;
  const radius = (size - strokeWidth) / 2;
  const circumference = Math.PI * radius; // half circle
  const offset = circumference * (1 - clamped / 100);
  const color = colorFor(clamped);

  if (!mounted) {
    return (
      <div className={cn("flex flex-col items-center", className)} style={{ width: size, height: size / 2 + 18 }} aria-hidden />
    );
  }

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <div className="relative" style={{ width: size, height: size / 2 + 18 }}>
        <svg width={size} height={size / 2 + 18} viewBox={`0 0 ${size} ${size / 2 + 18}`}>
          <path
            d={arcPath(size / 2, size / 2, radius, 180, 0)}
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          <motion.path
            d={arcPath(size / 2, size / 2, radius, 180, 0)}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: clamped / 100 }}
            transition={{ duration: 1, ease: "easeOut" }}
            style={{ transformOrigin: "center" }}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-x-0 top-[38%] flex flex-col items-center">
          <span className="text-3xl font-bold tabular-nums" style={{ color }}>
            {clamped.toFixed(0)}
          </span>
          {label && <span className="text-xs font-medium text-muted-foreground">{label}</span>}
          {sublabel && <span className="text-[11px] text-muted-foreground/80">{sublabel}</span>}
        </div>
      </div>
    </div>
  );
}

function arcPath(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, startAngle);
  const end = polarToCartesian(cx, cy, r, endAngle);
  return `M ${start.x} ${start.y} A ${r} ${r} 0 0 1 ${end.x} ${end.y}`;
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const angleRad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(angleRad), y: cy - r * Math.sin(angleRad) };
}
