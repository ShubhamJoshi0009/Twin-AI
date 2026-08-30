#!/usr/bin/env node
/**
 * Generates frontend/src/lib/map/world-paths.ts from world-atlas TopoJSON.
 *
 * Usage:  node scripts/generate-world-map.mjs <input-topojson> [output-ts]
 * The input is the unpkg world-atlas @2.0.2 countries-110m.json file.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const input = process.argv[2] ?? "/tmp/world-countries-110m.json";
const output = process.argv[3] ?? resolve(import.meta.dirname, "../src/lib/map/world-paths.ts");

const topo = JSON.parse(readFileSync(input, "utf8"));
const { transform } = topo;
const [sx, sy] = transform.scale;
const [tx, ty] = transform.translate;

// Decode quantized delta-encoded arcs into [lng, lat] coordinate lists.
const arcs = topo.arcs.map((arc) => {
  const pts = [];
  let x = 0;
  let y = 0;
  for (let i = 0; i < arc.length; i++) {
    x += arc[i][0];
    y += arc[i][1];
    pts.push([x * sx + tx, y * sy + ty]);
  }
  return pts;
});

const getArc = (idx) => (idx >= 0 ? arcs[idx] : [...arcs[~idx]].reverse());

const W = 1024;
const H = 512;
const project = (lng, lat) => [((lng + 180) / 360) * W, ((90 - lat) / 180) * H];

const TOL = 0.6;
const simplify = (pts) => {
  const out = [pts[0]];
  for (const p of pts.slice(1)) {
    const dx = p[0] - out[out.length - 1][0];
    const dy = p[1] - out[out.length - 1][1];
    if (dx * dx + dy * dy > TOL * TOL) out.push(p);
  }
  return out;
};

const paths = [];
for (const geom of topo.objects.countries.geometries) {
  const polys = geom.type === "Polygon" ? [geom.arcs] : geom.arcs;
  for (const poly of polys) {
    let d = "";
    for (const ring of poly) {
      let ringPts = getArc(ring[0]);
      for (const extra of ring.slice(1)) ringPts = ringPts.concat(getArc(extra).slice(1));
      const proj = simplify(ringPts.map(([lng, lat]) => project(lng, lat)).map(([x, y]) => [Math.round(x * 10) / 10, Math.round(y * 10) / 10]));
      if (proj.length < 3) continue;
      d += `M${proj.map(([x, y]) => `${x},${y}`).join("L")}Z`;
    }
    if (d) paths.push(d);
  }
}

const body = `// Generated from world-atlas @2.0.2 countries-110m (equirectangular projection ${W}×${H}).
// Regenerate with: node scripts/generate-world-map.mjs <topojson>
export const WORLD_MAP_SIZE = { width: ${W}, height: ${H} } as const;
export const WORLD_MAP_PATHS: string[] = [
${paths.map((p) => `  ${JSON.stringify(p)},`).join("\n")}
];
`;

writeFileSync(output, body);
console.log(`Wrote ${paths.length} country paths -> ${output}`);
