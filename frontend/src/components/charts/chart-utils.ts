"use client";

import { CHART_COLORS } from "@/lib/constants";

/** Serialize the first <svg> inside a container element and download it as .svg. */
export function downloadChartSvg(containerId: string, filename: string) {
  const node = document.getElementById(containerId)?.querySelector("svg");
  if (!node) return;
  const clone = node.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const svgData = new XMLSerializer().serializeToString(clone);
  const blob = new Blob(['<?xml version="1.0" standalone="no"?>\r\n' + svgData], {
    type: "image/svg+xml;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.svg`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Download a dataset as CSV. */
export function downloadCsv<T extends Record<string, unknown>>(
  rows: T[],
  filename: string,
  columns?: Array<{ key: string; label: string }>
) {
  if (!rows.length) return;
  const cols = columns ?? Object.keys(rows[0]).map((k) => ({ key: k, label: k }));
  const header = cols.map((c) => c.label).join(",");
  const body = rows
    .map((row) =>
      cols
        .map((c) => {
          const v = row[c.key];
          if (typeof v === "number") return v.toFixed(2);
          return `"${String(v ?? "").replaceAll('"', '""')}"`;
        })
        .join(",")
    )
    .join("\n");
  const blob = new Blob([`${header}\n${body}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function colorAt(index: number) {
  return CHART_COLORS[index % CHART_COLORS.length];
}

export function withAlpha(color: string, alpha: number) {
  if (color.startsWith("hsl")) {
    return color.replace("hsl(", "hsl(").replace(")", ` / ${alpha})`);
  }
  return color;
}
