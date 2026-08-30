"use client";

import { Menu, Search } from "lucide-react";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Notifications } from "@/components/layout/notifications";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { UserMenu } from "@/components/layout/user-menu";
import { BREADCRUMB_OVERRIDES } from "@/lib/constants";

interface TopbarProps {
  onOpenMobileNav: () => void;
  onOpenCommandPalette: () => void;
}

/** Sticky top bar with breadcrumbs and global actions. */
export function Topbar({ onOpenMobileNav, onOpenCommandPalette }: TopbarProps) {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);
  const current = segments[segments.length - 1] ?? "dashboard";

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-xl lg:px-6">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onOpenMobileNav} aria-label="Open navigation">
        <Menu className="h-4 w-4" />
      </Button>

      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>Business Twin AI</BreadcrumbItem>
          {segments.length > 1 && <BreadcrumbSeparator />}
          {segments.length > 1 && (
            <BreadcrumbItem>
              <BreadcrumbPage>{BREADCRUMB_OVERRIDES[current] ?? current}</BreadcrumbPage>
            </BreadcrumbItem>
          )}
        </BreadcrumbList>
      </Breadcrumb>

      <div className="ml-auto flex items-center gap-1.5">
        <Button
          variant="ghost"
          size="sm"
          className="hidden gap-2 text-muted-foreground md:flex"
          onClick={onOpenCommandPalette}
          aria-label="Open command palette"
        >
          <Search className="h-4 w-4" />
          <span className="text-sm">Search…</span>
          <kbd className="rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium">⌘K</kbd>
        </Button>
        <Button variant="ghost" size="icon" className="md:hidden" onClick={onOpenCommandPalette} aria-label="Search">
          <Search className="h-4 w-4" />
        </Button>
        <Notifications />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
