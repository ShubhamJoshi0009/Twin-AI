"use client";

import { useMemo } from "react";
import { MapPin, Route } from "lucide-react";
import { WORLD_MAP_PATHS, WORLD_MAP_SIZE } from "@/lib/map/world-paths";
import { formatNumber } from "@/lib/utils";

/**
 * City → coordinates lookup (equirectangular projection, same as the world
 * map). Shipment origins/destinations are free-text city names, so we match
 * by substring against known hubs.
 */
const CITY_COORDS: Array<{ match: string[]; lat: number; lng: number }> = [
  { match: ["shenzhen", "guangzhou"], lat: 22.54, lng: 114.06 },
  { match: ["shanghai"], lat: 31.23, lng: 121.47 },
  { match: ["chicago"], lat: 41.88, lng: -87.63 },
  { match: ["hamburg"], lat: 53.55, lng: 9.99 },
  { match: ["munich"], lat: 48.14, lng: 11.58 },
  { match: ["santiago"], lat: -33.45, lng: -70.67 },
  { match: ["newark"], lat: 40.74, lng: -74.17 },
  { match: ["new york", "nyc"], lat: 40.71, lng: -74.01 },
  { match: ["dallas"], lat: 32.78, lng: -96.8 },
  { match: ["reno"], lat: 39.53, lng: -119.81 },
  { match: ["los angeles"], lat: 34.05, lng: -118.24 },
  { match: ["houston"], lat: 29.76, lng: -95.37 },
  { match: ["miami"], lat: 25.76, lng: -80.19 },
  { match: ["rotterdam"], lat: 51.92, lng: 4.48 },
  { match: ["singapore"], lat: 1.35, lng: 103.82 },
  { match: ["mumbai"], lat: 18.94, lng: 72.83 },
];

function findCoord(city: string) {
  const key = city.toLowerCase();
  for (const c of CITY_COORDS) {
    if (c.match.some((m) => key.includes(m))) return { lat: c.lat, lng: c.lng };
  }
  return null;
}

/**
 * World-map route preview for a single shipment: draws the origin → destination
 * corridor as an animated arc over a stylised world map.
 */
export function ShipmentRouteMap({
  origin,
  destination,
  distanceKm,
  className,
}: {
  origin: string;
  destination: string;
  distanceKm?: number | null;
  className?: string;
}) {
  const { width, height } = WORLD_MAP_SIZE;

  const project = (lat: number, lng: number) => ({
    x: ((lng + 180) / 360) * width,
    y: ((90 - lat) / 180) * height,
  });

  const { a, b } = useMemo(() => {
    const o = findCoord(origin);
    const d = findCoord(destination);
    if (!o || !d) return { a: null, b: null };
    return { a: project(o.lat, o.lng), b: project(d.lat, d.lng) };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin, destination]);

  const known = a !== null && b !== null;

  // Gentle arc bulging toward the pole so the corridor reads as a route.
  const d = known ? `M ${a.x} ${a.y} Q ${(a.x + b.x) / 2} ${Math.min(a.y, b.y) - 26} ${b.x} ${b.y}` : "";
  const mid = known ? { x: (a.x + b.x) / 2, y: Math.min(a.y, b.y) - 34 } : null;

  return (
    <div className={className ?? ""}>
      <div className="relative w-full overflow-hidden rounded-lg border bg-[#0b1220]">
        <svg viewBox={`0 0 ${width} ${height}`} className="block w-full" role="img" aria-label={`Route map from ${origin} to ${destination}`}>
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
            {WORLD_MAP_PATHS.map((p, i) => (
              <path key={i} d={p} />
            ))}
          </g>

          {known ? (
            <g>
              {/* Route corridor */}
              <path d={d} fill="none" stroke="rgba(56,189,248,0.3)" strokeWidth={5} strokeLinecap="round" />
              <path
                d={d}
                fill="none"
                stroke="#38bdf8"
                strokeWidth={2}
                strokeLinecap="round"
                strokeDasharray="7 6"
                style={{ animation: "dash 1.4s linear infinite" }}
              />
              {/* Origin marker */}
              <circle cx={a.x} cy={a.y} r={5} fill="#38bdf8" stroke="#0b1220" strokeWidth={1.5} />
              <text x={a.x + 7} y={a.y - 7} fill="#e2e8f0" fontSize={11} fontWeight={600} className="pointer-events-none">
                {origin.split(",")[0]}
              </text>
              {/* Destination marker */}
              <circle cx={b.x} cy={b.y} r={5} fill="#a78bfa" stroke="#0b1220" strokeWidth={1.5} />
              <text x={b.x + 7} y={b.y - 7} fill="#e2e8f0" fontSize={11} fontWeight={600} className="pointer-events-none">
                {destination.split(",")[0]}
              </text>
              {/* Mid label */}
              {mid && (
                <text x={mid.x} y={mid.y} fill="#94a3b8" fontSize={10} textAnchor="middle" className="pointer-events-none">
                  {distanceKm ? `${formatNumber(distanceKm)} km` : "route"}
                </text>
              )}
            </g>
          ) : (
            <text x={width / 2} y={height / 2} fill="#64748b" fontSize={12} textAnchor="middle">
              Route preview unavailable for these cities
            </text>
          )}
        </svg>

        {/* Status chip */}
        <div className="absolute left-2.5 top-2.5 flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-950/70 px-2.5 py-1 backdrop-blur">
          <Route className="h-3 w-3 text-sky-400" />
          <span className="text-[10px] font-semibold text-sky-300">
            {origin.split(",")[0]} → {destination.split(",")[0]}
          </span>
        </div>
        {known && (
          <div className="absolute bottom-2.5 right-2.5 flex items-center gap-1.5 rounded-md bg-black/40 px-2 py-1 text-[10px] text-slate-300 backdrop-blur">
            <MapPin className="h-3 w-3 text-slate-400" />
            {distanceKm ? `${formatNumber(distanceKm)} km · by sea/land` : "route corridor"}
          </div>
        )}
      </div>
    </div>
  );
}

/** Keyframe helper so the dashed route animation has a definition. */
export const routeMapDashKeyframes = `
@keyframes dash {
  to { stroke-dashoffset: -26; }
}
`;
