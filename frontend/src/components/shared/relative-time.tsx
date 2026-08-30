"use client";

import { useMounted } from "@/hooks/use-mounted";
import { timeAgo } from "@/lib/utils";

interface RelativeTimeProps {
  value: string | Date | null | undefined;
  className?: string;
}

/**
 * Renders "3h ago" style timestamps. Because the value depends on the current
 * clock, it only renders on the client to keep SSR HTML and client HTML in sync.
 */
export function RelativeTime({ value, className }: RelativeTimeProps) {
  const mounted = useMounted();
  if (!mounted) return <span className={className}>—</span>;
  return <span className={className}>{timeAgo(value)}</span>;
}
