"use client";

import { useEffect, useState } from "react";

/**
 * Returns true once the component has mounted on the client.
 * Used to defer rendering of measurement- or time-dependent UI (charts,
 * React Flow canvases, relative timestamps) so the server-rendered HTML
 * matches the client's first render — avoiding React hydration mismatches.
 */
export function useMounted() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  return mounted;
}
