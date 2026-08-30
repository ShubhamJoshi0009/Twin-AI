"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Bell, CheckCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { RelativeTime } from "@/components/shared/relative-time";
import { useAlerts } from "@/hooks/use-api";

const SEVERITY_ORDER: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
const MAX_ITEMS = 6;

/**
 * Header notifications bell — surfaces the latest operational alerts
 * (severity-first, newest within each band) and links to the full Alerts
 * Center via "See all alerts". Acknowledging alerts only affects this bell.
 */
export function Notifications() {
  const { data: alerts } = useAlerts();
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());

  const items = useMemo(() => {
    const active = (alerts ?? []).filter((a) => a.status !== "resolved");
    return [...active]
      .sort((a, b) => {
        const sev = (SEVERITY_ORDER[b.severity] ?? 0) - (SEVERITY_ORDER[a.severity] ?? 0);
        return sev !== 0 ? sev : +new Date(b.created_at) - +new Date(a.created_at);
      })
      .slice(0, MAX_ITEMS);
  }, [alerts]);

  const totalActive = (alerts ?? []).filter((a) => a.status !== "resolved").length;
  const unread = items.filter((a) => !acknowledged.has(a.id)).length;

  const acknowledge = (id: string) =>
    setAcknowledged((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));

  const markAllRead = () =>
    setAcknowledged((prev) => new Set([...prev, ...items.map((a) => a.id)]));

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={`Notifications (${unread} unread)`}>
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <motion.span
              key={unread}
              initial={{ scale: 0.4 }}
              animate={{ scale: 1 }}
              className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground"
            >
              {unread}
            </motion.span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span>Notifications</span>
          <Button variant="ghost" size="icon-sm" onClick={markAllRead} disabled={unread === 0} aria-label="Mark all as read">
            <CheckCheck className="h-4 w-4" />
          </Button>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="max-h-80 overflow-y-auto">
          {items.length === 0 && (
            <p className="p-4 text-center text-sm text-muted-foreground">All caught up 🎉</p>
          )}
          {items.map((n) => {
            const isRead = acknowledged.has(n.id);
            return (
              <button
                key={n.id}
                onClick={() => acknowledge(n.id)}
                className="flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-accent/60"
              >
                <span
                  className={
                    isRead
                      ? "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-transparent"
                      : "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
                  }
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{n.title}</span>
                    <SeverityBadge severity={n.severity} className="shrink-0 !px-1.5 !text-[10px]" />
                  </span>
                  <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">{n.description}</span>
                  <span className="mt-1 block text-[10px] text-muted-foreground/70">
                    <RelativeTime value={n.created_at} /> · {n.alert_type.replace("_", " ")}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
        <DropdownMenuSeparator />
        <Link
          href="/alerts"
          className="flex items-center justify-between gap-2 px-3 py-2.5 text-sm font-medium text-primary transition-colors hover:bg-accent/60"
        >
          See all alerts {totalActive > 0 ? `(${totalActive} active)` : ""}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
