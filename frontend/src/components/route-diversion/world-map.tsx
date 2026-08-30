"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { CloudRain, CloudSun } from "lucide-react";
import { WORLD_MAP_PATHS, WORLD_MAP_SIZE } from "@/lib/map/world-paths";
import type {
  ChokepointInfo,
  RoutePathPayload,
  RoutePort,
  RouteSegmentInfo,
  RouteWeatherResponse,
} from "@/lib/types";
import { cn, stringToHue } from "@/lib/utils";

/** Risk level → color + label used for the weather overlay. */
export const WEATHER_LEVEL_STYLES: Record<
  string,
  { color: string; label: string; glow: string }
> = {
  GREEN: { color: "#22c55e", label: "Clear", glow: "rgba(34,197,94,0.35)" },
  YELLOW: { color: "#eab308", label: "Caution", glow: "rgba(234,179,8,0.35)" },
  ORANGE: { color: "#f97316", label: "High risk", glow: "rgba(249,115,22,0.45)" },
  RED: { color: "#ef4444", label: "Severe", glow: "rgba(239,68,68,0.5)" },
};

export function weatherLevelColor(level: string): string {
  return WEATHER_LEVEL_STYLES[level]?.color ?? "#94a3b8";
}

/**
 * Interactive world map (equirectangular projection) with the shipping
 * network overlaid. Chokepoints can be clicked to block them; the baseline
 * and diverted routes are drawn as animated polylines.
 */
export function WorldMap({
  ports,
  segments,
  chokepoints,
  blocked,
  baseline,
  diverted,
  originId,
  destinationId,
  selectedChokepoint,
  onSelectChokepoint,
  weather,
}: {
  ports: RoutePort[];
  segments: RouteSegmentInfo[];
  chokepoints: ChokepointInfo[];
  blocked: string[];
  baseline?: RoutePathPayload | null;
  diverted?: RoutePathPayload | null;
  originId?: string | null;
  destinationId?: string | null;
  selectedChokepoint?: string | null;
  onSelectChokepoint?: (id: string | null) => void;
  /** Real-time weather overlay: per-port conditions + per-lane risk. */
  weather?: RouteWeatherResponse | null;
}) {
  const { width, height } = WORLD_MAP_SIZE;

  const portById = useMemo(() => new Map(ports.map((p) => [p.id, p])), [ports]);

  // Weather lookups: port id → conditions/risk, and lane key → lane risk.
  const weatherByPort = useMemo(() => {
    const map = new Map<string, RouteWeatherResponse["ports"][number]>();
    for (const pw of weather?.ports ?? []) map.set(pw.port_id, pw);
    return map;
  }, [weather]);
  const weatherByLane = useMemo(() => {
    const map = new Map<string, RouteWeatherResponse["lanes"][number]>();
    for (const lw of weather?.lanes ?? []) map.set(`${lw.from}__${lw.to}`, lw);
    return map;
  }, [weather]);
  const worstWeatherLevel = weather?.summary.worst_level ?? null;

  const project = (lat: number, lng: number) => ({
    x: ((lng + 180) / 360) * width,
    y: ((90 - lat) / 180) * height,
  });

  const pathFor = (p: RoutePathPayload | null | undefined) => {
    if (!p || !p.port_ids?.length) return null;
    const pts = p.port_ids
      .map((id) => portById.get(id))
      .filter(Boolean) as RoutePort[];
    if (pts.length < 2) return null;
    return pts
      .map((pt, i) => `${i === 0 ? "M" : "L"}${project(pt.lat, pt.lng).x.toFixed(1)},${project(pt.lat, pt.lng).y.toFixed(1)}`)
      .join("");
  };

  const baselinePath = pathFor(baseline);
  const divertedPath = pathFor(diverted);

  const chokepointSegments = useMemo(() => {
    const map = new Map<string, Array<{ from: RoutePort; to: RoutePort; segment: RouteSegmentInfo }>>();
    for (const seg of segments) {
      if (!seg.chokepoint) continue;
      const from = portById.get(seg.from);
      const to = portById.get(seg.to);
      if (!from || !to) continue;
      const list = map.get(seg.chokepoint) ?? [];
      list.push({ from, to, segment: seg });
      map.set(seg.chokepoint, list);
    }
    return map;
  }, [segments, portById]);

  // Land corridors (rail bridges) are drawn in violet to stand out from the
  // amber maritime chokepoints.
  const kindById = useMemo(() => new Map(chokepoints.map((cp) => [cp.id, cp.kind ?? "maritime"])), [chokepoints]);

  return (
    <div className="relative w-full overflow-hidden rounded-xl border bg-[#0b1220]">
      <svg viewBox={`0 0 ${width} ${height}`} className="block w-full" role="img" aria-label="World shipping map">
        {/* Ocean */}
        <rect width={width} height={height} fill="#0b1220" />

        {/* Graticule */}
        <g stroke="rgba(148,163,184,0.07)" strokeWidth={0.5}>
          {Array.from({ length: 13 }, (_, i) => (
            <line key={`lat-${i}`} x1={0} y1={(i * height) / 12} x2={width} y2={(i * height) / 12} />
          ))}
          {Array.from({ length: 25 }, (_, i) => (
            <line key={`lng-${i}`} x1={(i * width) / 24} y1={0} x2={(i * width) / 24} y2={height} />
          ))}
        </g>

        {/* Land */}
        <g fill="#1e293b" stroke="#334155" strokeWidth={0.4}>
          {WORLD_MAP_PATHS.map((d, i) => (
            <path key={i} d={d} />
          ))}
        </g>

        {/* Sea lanes (tinted by weather risk when the overlay is live) */}
        {segments.map((seg) => {
          const from = portById.get(seg.from);
          const to = portById.get(seg.to);
          if (!from || !to) return null;
          const a = project(from.lat, from.lng);
          const b = project(to.lat, to.lng);
          const isLand = seg.chokepoint ? kindById.get(seg.chokepoint) === "land" : false;
          const laneWeather = weatherByLane.get(`${seg.from}__${seg.to}`) ?? weatherByLane.get(`${seg.to}__${seg.from}`);
          const tint = laneWeather ? weatherLevelColor(laneWeather.risk_level) : null;
          return (
            <line
              key={seg.id}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={
                tint
                  ? isLand
                    ? `${tint}55` // alpha-hex suffix → ~33% opacity
                    : `${tint}45`
                  : isLand
                    ? "rgba(192,132,252,0.28)"
                    : "rgba(56,189,248,0.18)"
              }
              strokeWidth={isLand ? 1.4 : 1}
              strokeDasharray={isLand ? "2 3" : undefined}
            />
          );
        })}

        {/* Chokepoint segments (thicker, hoverable) */}
        {chokepoints.map((cp) => {
          const segs = chokepointSegments.get(cp.id) ?? [];
          const isBlocked = blocked.includes(cp.id);
          const isSelected = selectedChokepoint === cp.id;
          return segs.map(({ from, to, segment }, i) => {
            const a = project(from.lat, from.lng);
            const b = project(to.lat, to.lng);
            return (
              <g
                key={`${cp.id}-${i}`}
                onClick={() => (onSelectChokepoint ? onSelectChokepoint(isSelected ? null : cp.id) : undefined)}
                className="cursor-pointer"
              >
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  strokeWidth={7}
                  stroke="transparent"
                  className="hover:stroke-white/10"
                />
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={
                    isBlocked
                      ? "#f87171"
                      : cp.kind === "land"
                        ? isSelected
                          ? "#c084fc"
                          : "#a855f7"
                        : isSelected
                          ? "#fbbf24"
                          : "#f59e0b"
                  }
                  strokeWidth={2.5}
                  strokeDasharray={isBlocked ? "2 4" : cp.kind === "land" ? "2 4" : "6 4"}
                  className="animate-pulse"
                  opacity={isBlocked ? 1 : 0.8}
                />
              </g>
            );
          });
        })}

        {/* Baseline route */}
        {baselinePath && (
          <g>
            <path
              d={baselinePath}
              fill="none"
              stroke="rgba(56,189,248,0.35)"
              strokeWidth={4}
              strokeLinecap="round"
            />
            <path
              d={baselinePath}
              fill="none"
              stroke="#38bdf8"
              strokeWidth={2}
              strokeLinecap="round"
              strokeDasharray="8 6"
              className="animate-[dash_1.2s_linear_infinite]"
              style={{ animation: "dash 1.4s linear infinite" }}
            />
          </g>
        )}

        {/* Diverted route */}
        {divertedPath && divertedPath !== baselinePath && (
          <g>
            <path
              d={divertedPath}
              fill="none"
              stroke="rgba(74,222,128,0.4)"
              strokeWidth={4}
              strokeLinecap="round"
            />
            <path
              d={divertedPath}
              fill="none"
              stroke="#4ade80"
              strokeWidth={2}
              strokeLinecap="round"
              strokeDasharray="4 8"
              style={{ animation: "dash 1.8s linear infinite" }}
            />
          </g>
        )}

        {/* Ports (with weather rings when the overlay is active) */}
        {ports.map((p) => {
          const pos = project(p.lat, p.lng);
          const isOrigin = p.id === originId;
          const isDest = p.id === destinationId;
          const hue = stringToHue(p.id);
          const pw = weatherByPort.get(p.id);
          const wStyle = pw ? WEATHER_LEVEL_STYLES[pw.risk_level] : null;
          return (
            <g key={p.id}>
              {pw && wStyle && pw.risk_level !== "GREEN" && (
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={isOrigin || isDest ? 10 : 8}
                  fill={wStyle.glow}
                  stroke={wStyle.color}
                  strokeWidth={1.2}
                  className={pw.risk_level === "RED" ? "animate-pulse" : undefined}
                />
              )}
              <circle cx={pos.x} cy={pos.y} r={isOrigin || isDest ? 5 : 3} fill={isOrigin ? "#38bdf8" : isDest ? "#a78bfa" : `hsl(${hue} 60% 60%)`} stroke="#0b1220" strokeWidth={1.2} />
              {(isOrigin || isDest) && (
                <text x={pos.x + 6} y={pos.y - 6} fill="#e2e8f0" fontSize={11} fontWeight={600} className="pointer-events-none">
                  {p.name}
                </text>
              )}
              {/* Weather chip on origin/destination ports */}
              {pw && (isOrigin || isDest) && (
                <text x={pos.x + 6} y={pos.y + 14} fill="#94a3b8" fontSize={10} className="pointer-events-none">
                  {pw.conditions.weather_icon} {pw.conditions.temperature_c.toFixed(0)}°C · {pw.risk_level}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Blocked chokepoint badge */}
      {blocked.length > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="absolute right-3 top-3 flex items-center gap-2 rounded-full border border-red-500/40 bg-red-950/70 px-3 py-1.5 backdrop-blur"
        >
          <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
          <span className="text-[11px] font-semibold text-red-300">{blocked.length} chokepoint{blocked.length > 1 ? "s" : ""} blocked</span>
        </motion.div>
      )}

      {/* Live weather badge */}
      {weather && worstWeatherLevel && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="absolute left-3 top-3 flex items-center gap-2 rounded-full border bg-slate-950/70 px-3 py-1.5 backdrop-blur"
          style={{ borderColor: `${weatherLevelColor(worstWeatherLevel)}66` }}
        >
          <CloudSun className="h-3.5 w-3.5" style={{ color: weatherLevelColor(worstWeatherLevel) }} />
          <span className="text-[11px] font-semibold" style={{ color: weatherLevelColor(worstWeatherLevel) }}>
            Weather · {worstWeatherLevel}
          </span>
          {weather.alerts.length > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-red-500/20 px-1.5 py-0.5 text-[10px] font-medium text-red-300">
              <CloudRain className="h-3 w-3" /> {weather.alerts.length}
            </span>
          )}
        </motion.div>
      )}
    </div>
  );
}

/** Keyframe helper so the dashed route animation has a definition. */
export const mapDashKeyframes = `
@keyframes dash {
  to { stroke-dashoffset: -24; }
}
`;
