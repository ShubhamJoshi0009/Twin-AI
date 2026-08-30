"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface QuickNavItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Sticky "on this page" chip bar with scroll-spy. Clicking a chip smooth-scrolls
 * to the matching section; sections opt into the offset via Tailwind's
 * `scroll-mt-28` (and the global `:target { scroll-margin-top }` rule), so the
 * target lands below the sticky topbar + chip bar. Honors prefers-reduced-motion.
 */
export function QuickNav({ items, className }: { items: QuickNavItem[]; className?: string }) {
  const [activeId, setActiveId] = useState<string>(items[0]?.id ?? "");
  const sectionsRef = useRef<HTMLElement[]>([]);
  const navRef = useRef<HTMLElement | null>(null);
  const itemsRef = useRef(items);
  itemsRef.current = items;

  useEffect(() => {
    let raf = 0;

    const collect = () => {
      sectionsRef.current = itemsRef.current
        .map((i) => document.getElementById(i.id))
        .filter((el): el is HTMLElement => el !== null);
    };

    // The section whose top has crossed the nav line is the active one.
    const update = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const els = sectionsRef.current;
        if (!els.length) return;
        const navBottom = navRef.current?.getBoundingClientRect().bottom ?? 100;
        let current = els[0].id;
        for (const el of els) {
          if (el.getBoundingClientRect().top <= navBottom) current = el.id;
        }
        setActiveId(current);
      });
    };

    collect();
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);

    // Sections may mount lazily after data loads — watch only this page's
    // content container (the QuickNav's parent), not the whole document.
    const scope = navRef.current?.parentElement ?? document.body;
    const observer = new MutationObserver(() => {
      collect();
      update();
    });
    observer.observe(scope, { childList: true, subtree: true });

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      observer.disconnect();
    };
  }, []);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    // scrollIntoView respects the section's scroll-margin (scroll-mt-28),
    // landing it just below the sticky topbar + chip bar.
    el.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    setActiveId(id);
  };

  if (items.length === 0) return null;

  return (
    <nav
      ref={navRef}
      aria-label="On this page"
      className={cn(
        "sticky top-14 z-20 flex items-center gap-1.5 overflow-x-auto border-b bg-background/85 px-1 py-2 backdrop-blur-xl lg:rounded-xl lg:border lg:px-2",
        className
      )}
    >
      {items.map((item) => (
        <button
          key={item.id}
          onClick={() => scrollTo(item.id)}
          aria-current={activeId === item.id ? "true" : undefined}
          className={cn(
            "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-medium transition-all",
            activeId === item.id
              ? "border-primary/50 bg-primary/15 text-primary shadow-sm"
              : "border-border bg-card text-muted-foreground hover:border-foreground/40 hover:text-foreground"
          )}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </nav>
  );
}
