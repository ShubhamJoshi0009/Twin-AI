"use client";

import * as React from "react";
import { Download, MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { downloadChartSvg, downloadCsv } from "@/components/charts/chart-utils";
import { cn } from "@/lib/utils";

interface ChartCardProps {
  id: string;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  actions?: React.ReactNode;
  csvData?: Array<Record<string, unknown>>;
  csvColumns?: Array<{ key: string; label: string }>;
  footer?: React.ReactNode;
  height?: number;
}

/** Card wrapper that gives every chart a title, hover actions and export (SVG/CSV). */
export function ChartCard({
  id,
  title,
  description,
  children,
  className,
  contentClassName,
  actions,
  csvData,
  csvColumns,
  footer,
  height,
}: ChartCardProps) {
  return (
    <Card id={id} className={cn("group transition-shadow hover:shadow-md", className)}>
      <CardHeader className="flex-row items-start justify-between space-y-0 pb-3">
        <div className="space-y-1">
          <CardTitle className="text-sm font-semibold">{title}</CardTitle>
          {description && <CardDescription className="text-xs">{description}</CardDescription>}
        </div>
        <div className="flex items-center gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          {actions}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Export chart">
                <Download className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => downloadChartSvg(id, title.toLowerCase().replaceAll(" ", "-"))}>
                Export as SVG
              </DropdownMenuItem>
              {csvData && (
                <DropdownMenuItem onClick={() => downloadCsv(csvData, title.toLowerCase().replaceAll(" ", "-"), csvColumns)}>
                  Export as CSV
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
        </div>
      </CardHeader>
      <CardContent className={cn("pt-0", contentClassName)} style={height ? { height } : undefined}>
        {children}
      </CardContent>
      {footer && <div className="border-t px-5 py-3">{footer}</div>}
    </Card>
  );
}
