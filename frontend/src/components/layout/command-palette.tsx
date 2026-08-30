"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { CornerDownLeft, Search } from "lucide-react";
import { NAV_ITEMS } from "@/lib/constants";
import { iconByName } from "@/lib/icon-map";
import { cn } from "@/lib/utils";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

/** ⌘K command palette: fuzzy navigates to any page. */
export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const items = NAV_ITEMS.map((n) => ({ title: n.title, href: n.href, section: n.section, icon: n.icon }));
    if (!q) return items;
    return items.filter((i) => i.title.toLowerCase().includes(q) || i.href.includes(q));
  }, [query]);

  useEffect(() => setSelected(0), [query]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") { e.preventDefault(); setSelected((s) => Math.min(s + 1, results.length - 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)); }
      if (e.key === "Enter" && results[selected]) {
        router.push(results[selected].href);
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, results, selected, router, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh]" role="dialog" aria-modal aria-label="Command palette">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: -8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.15 }}
        className="relative w-full max-w-lg overflow-hidden rounded-xl border bg-popover shadow-2xl"
      >
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages…"
            className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            onKeyDown={(e) => e.key === "Escape" && onClose()}
          />
          <kbd className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">ESC</kbd>
        </div>
        <div className="max-h-72 overflow-y-auto p-2">
          {results.length === 0 && <p className="p-4 text-center text-sm text-muted-foreground">No results</p>}
          {results.map((r, i) => {
            const Icon = iconByName(r.icon);
            return (
              <button
                key={r.href}
                onClick={() => { router.push(r.href); onClose(); }}
                onMouseEnter={() => setSelected(i)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors",
                  i === selected ? "bg-accent" : "hover:bg-accent/60"
                )}
              >
                <Icon className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1">{r.title}</span>
                {i === selected && <CornerDownLeft className="h-3.5 w-3.5 text-muted-foreground" />}
              </button>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}
