"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  streaming?: boolean;
}

interface ChatState {
  messages: ChatMessage[];
  addMessage: (m: ChatMessage) => void;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  clearHistory: () => void;
}

/** Chat history shared across the app and persisted locally. */
export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      addMessage: (m) => set((state) => ({ messages: [...state.messages, m] })),
      updateMessage: (id, patch) =>
        set((state) => ({ messages: state.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)) })),
      clearHistory: () => set({ messages: [] }),
    }),
    { name: "bta-chat-history" }
  )
);
