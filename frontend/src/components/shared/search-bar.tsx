"use client";

import * as React from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/use-debounce";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  debounceMs?: number;
}

/** Search input that debounces onChange — used across lists, alerts, timeline. */
export function SearchBar({ value, onChange, placeholder = "Search…", className, debounceMs = 250 }: SearchBarProps) {
  const [raw, setRaw] = React.useState(value);
  const debounced = useDebounce(raw, debounceMs);

  React.useEffect(() => {
    onChange(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  React.useEffect(() => setRaw(value), [value]);

  return (
    <div className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        placeholder={placeholder}
        className="h-9 pl-9 pr-8"
        aria-label={placeholder}
      />
      {raw && (
        <button
          onClick={() => setRaw("")}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-full p-0.5 text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Clear search"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
