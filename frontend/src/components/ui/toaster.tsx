"use client";

import { Toaster as Sonner } from "sonner";

export function Toaster() {
  return (
    <Sonner
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast: "border-border bg-card text-card-foreground shadow-lg",
          description: "text-muted-foreground",
        },
      }}
    />
  );
}
