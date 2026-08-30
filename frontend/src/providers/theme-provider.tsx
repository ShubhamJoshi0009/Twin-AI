"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import { useEffect } from "react";
import type { ComponentProps } from "react";

export function ThemeProvider({ children, ...props }: ComponentProps<typeof NextThemesProvider>) {
  // Add a short transition class while the theme flips for a smooth cross-fade.
  useEffect(() => {
    // Guard against the removal timeout re-triggering the observer: removing
    // `theme-transition` is itself a class mutation, so without this the
    // observer + timeout loop forever, restarting transitions on every element
    // every 400ms → frozen / crashing tab.
    let applying = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const applyTransition = () => {
      if (applying) return;
      applying = true;
      document.documentElement.classList.add("theme-transition");
      clearTimeout(timer);
      timer = setTimeout(() => {
        document.documentElement.classList.remove("theme-transition");
        // The removal mutation is delivered as a microtask — release the guard
        // on the next frame, well after it, so it is ignored.
        requestAnimationFrame(() => {
          applying = false;
        });
      }, 300);
    };

    const observer = new MutationObserver((mutations) => {
      // Ignore mutations caused by our own class add/remove.
      if (applying) return;
      // Only react to a real theme flip (dark ⇄ light / system), not to any
      // other incidental class churn on <html>.
      const flipped = mutations.some(
        (m) =>
          m.type === "attributes" &&
          m.target === document.documentElement &&
          (m.oldValue ?? "").includes("dark") !==
            document.documentElement.classList.contains("dark")
      );
      if (flipped) applyTransition();
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
      attributeOldValue: true,
    });

    return () => {
      observer.disconnect();
      clearTimeout(timer);
      document.documentElement.classList.remove("theme-transition");
    };
  }, []);

  return (
    <NextThemesProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange {...props}>
      {children}
    </NextThemesProvider>
  );
}
