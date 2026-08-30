"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Activity, ChevronsLeft, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NAV_ITEMS } from "@/lib/constants";
import { iconByName } from "@/lib/icon-map";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const SECTIONS = ["Overview", "Decision Intelligence", "Supply Chain", "System"] as const;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

/** Enterprise sidebar: grouped navigation, collapsible, dark in both themes. */
export function Sidebar({ collapsed, onToggle, mobileOpen, onCloseMobile }: SidebarProps) {
  const pathname = usePathname();

  const content = (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 border-b border-sidebar-border px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 shadow-md">
          <Activity className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold leading-tight">Business Twin AI</p>
            <p className="truncate text-[10px] text-sidebar-foreground/60">Intelligence Platform</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-4" aria-label="Main navigation">
        {SECTIONS.map((section) => {
          const items = NAV_ITEMS.filter((n) => n.section === section);
          if (!items.length) return null;
          return (
            <div key={section}>
              {!collapsed && (
                <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/40">
                  {section}
                </p>
              )}
              <ul className="space-y-0.5">
                {items.map((item) => {
                  const Icon = iconByName(item.icon);
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  const link = (
                    <Link
                      href={item.href}
                      onClick={onCloseMobile}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-md px-2.5 py-2 text-sm font-medium transition-all duration-150",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId="sidebar-active"
                          className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary"
                        />
                      )}
                      <Icon className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-sidebar-foreground/60 group-hover:text-sidebar-foreground")} />
                      {!collapsed && <span className="truncate">{item.title}</span>}
                      {!collapsed && item.badge ? (
                        <span className="ml-auto rounded-full bg-primary/20 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                          {item.badge}
                        </span>
                      ) : null}
                    </Link>
                  );
                  return (
                    <li key={item.href}>
                      {collapsed ? (
                        <Tooltip>
                          <TooltipTrigger asChild>{link}</TooltipTrigger>
                          <TooltipContent side="right">{item.title}</TooltipContent>
                        </Tooltip>
                      ) : (
                        link
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-sidebar-border p-3">
        <button
          onClick={onToggle}
          className="flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden border-r border-sidebar-border bg-sidebar transition-all duration-300 lg:block",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {content}
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onCloseMobile} aria-hidden />
          <motion.aside
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="absolute inset-y-0 left-0 w-64 shadow-2xl"
          >
            {content}
          </motion.aside>
        </div>
      )}
    </>
  );
}
