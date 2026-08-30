"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

/** Renders a chat bubble. Assistant messages support markdown + a typewriter effect. */
export function ChatMessage({ role, content, streaming }: ChatMessageProps) {
  const isUser = role === "user";
  const [typed, setTyped] = useState(isUser ? content : "");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Typewriter effect for assistant messages while "streaming".
  useEffect(() => {
    if (isUser) return;
    if (!streaming) {
      setTyped(content);
      return;
    }
    let i = 0;
    timerRef.current = setInterval(() => {
      i += 3;
      setTyped(content.slice(0, i));
      if (i >= content.length && timerRef.current) {
        clearInterval(timerRef.current);
      }
    }, 18);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [content, streaming, isUser]);

  const isTyping = streaming && typed.length < content.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn("flex w-full gap-3", isUser ? "flex-row-reverse" : "")}
    >
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary/15 text-primary" : "bg-gradient-to-br from-blue-500 to-violet-600 text-white"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div className={cn("max-w-[82%] space-y-1", isUser && "flex flex-col items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
            isUser
              ? "rounded-tr-sm bg-primary text-primary-foreground"
              : "rounded-tl-sm border bg-card"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{content}</p>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-table:text-xs prose-th:text-left">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{typed}</ReactMarkdown>
            </div>
          )}
        </div>
        {isTyping && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <span className="h-1 w-1 animate-bounce rounded-full bg-current" />
            <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:120ms]" />
            <span className="h-1 w-1 animate-bounce rounded-full bg-current [animation-delay:240ms]" />
            thinking…
          </span>
        )}
      </div>
    </motion.div>
  );
}
