"use client";

import { motion } from "framer-motion";
import { Newspaper, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RelativeTime } from "@/components/shared/relative-time";
import type { NewsItem } from "@/lib/types";

/** Real-time market headlines grounding the analysis (GDELT or curated). */
export function NewsPanel({
  news,
  query,
  limit = 4,
}: {
  news: NewsItem[];
  query?: string;
  limit?: number;
}) {
  const items = (news ?? []).slice(0, limit);
  if (!items.length) return null;
  return (
    <Card className="border-chart-1/30 bg-chart-1/5">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Newspaper className="h-4 w-4 text-chart-1" />
          Market News — grounding the analysis
        </CardTitle>
        {query && <Badge variant="secondary" className="max-w-40 truncate text-[10px]">{query}</Badge>}
      </CardHeader>
      <CardContent className="space-y-2.5">
        {items.map((n, i) => (
          <motion.a
            key={`${n.source}-${i}`}
            href={n.url}
            target="_blank"
            rel="noreferrer"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="group block rounded-lg border border-border/60 bg-card/80 p-3 transition-all hover:-translate-y-0.5 hover:border-chart-1/40 hover:shadow-sm"
          >
            <p className="line-clamp-2 text-sm font-medium group-hover:text-chart-1">{n.title}</p>
            <p className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="font-semibold">{n.source}</span>
              {n.published_at && (
                <>
                  <span>·</span>
                  <RelativeTime value={n.published_at} />
                </>
              )}
            </p>
          </motion.a>
        ))}
        <p className="flex items-center gap-1.5 pt-1 text-[11px] text-muted-foreground">
          <Sparkles className="h-3 w-3 text-chart-1" />
          Live headlines from GDELT — the recommendation above weighs this real-time context.
        </p>
      </CardContent>
    </Card>
  );
}
