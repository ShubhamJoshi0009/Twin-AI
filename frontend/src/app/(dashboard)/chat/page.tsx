"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUp, Bot, Eraser, Sparkles, User } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { ChatMessage } from "@/components/chat/chat-message";
import { OnboardingConversation } from "@/components/chat/onboarding-conversation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useChatStore, type ChatMessage as ChatMessageType } from "@/stores/chat-store";
import { needsProfileSetup, useProfileStore } from "@/stores/profile-store";
import { useMounted } from "@/hooks/use-mounted";
import { useTwins } from "@/hooks/use-api";
import * as business from "@/lib/api/business";
import * as sc from "@/lib/api/supply-chain";
import * as agentic from "@/lib/api/agentic";
import { errorMessage } from "@/lib/api/client";
import { firstName, personalizedQuestions } from "@/lib/personalization";
import { SUGGESTED_QUESTIONS } from "@/lib/constants";
import { isDemoTwinId, MOCK_AGENT_RESPONSE, MOCK_SC_AGENT_RESPONSE } from "@/lib/mock/mock-data";
import { uid } from "@/lib/utils";

const SUPPLY_CHAIN_KEYWORDS = ["supplier", "inventory", "warehouse", "shipment", "logistics", "supply chain", "risk", "route"];

function detectSupplyChain(question: string) {
  const q = question.toLowerCase();
  return SUPPLY_CHAIN_KEYWORDS.some((k) => q.includes(k));
}

export default function ChatPage() {
  const { data: twins } = useTwins();
  const twinId = twins?.[0]?.id ?? null;
  const realTwinId = twinId && !isDemoTwinId(twinId) ? twinId : null;
  const mounted = useMounted();
  const { messages, addMessage, updateMessage, clearHistory } = useChatStore();
  const profile = useProfileStore();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const setupNeeded = needsProfileSetup(profile);

  // `?setup=1` (e.g. from Settings) opens the personalisation conversation.
  useEffect(() => {
    if (window.location.search.includes("setup=1")) {
      setSetupOpen(true);
      window.history.replaceState(null, "", "/chat");
    }
  }, []);

  // Auto scroll to the latest message.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, setupOpen]);

  const suggested = useMemo(
    () => (setupNeeded ? SUGGESTED_QUESTIONS : personalizedQuestions(profile.business, profile.personal)),
    [setupNeeded, profile.business, profile.personal]
  );

  const greeting = useMemo(() => {
    if (profile.personal.name) return `Good to see you, ${firstName(profile.personal.name)}`;
    if (profile.business.name) return `Welcome — ${profile.business.name} at your fingertips`;
    return "How can I help you today?";
  }, [profile.personal.name, profile.business.name]);

  const onSetupDone = ({ twinUpdated }: { twinUpdated: boolean }) => {
    setSetupOpen(false);
    addMessage({
      id: uid("m"),
      role: "assistant",
      content:
        "✅ **Workspace personalised** — your profile and " +
        (twinUpdated ? "digital twin have been updated" : "preferences have been saved locally") +
        " to match your business. Just ask me anything in the composer below.",
      timestamp: new Date().toISOString(),
    });
  };

  const send = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || busy) return;
    setInput("");
    setBusy(true);

    const userMsg: ChatMessageType = { id: uid("m"), role: "user", content: trimmed, timestamp: new Date().toISOString() };
    const assistantId = uid("m");
    addMessage(userMsg);
    addMessage({ id: assistantId, role: "assistant", content: "", timestamp: new Date().toISOString(), streaming: true });

    try {
      // Agentic mode: when a real twin exists, deploy the full 4-agent team
      // (financial / market / supply chain / strategy) with a visible trace.
      let answer = "";
      let trace = "";
      if (realTwinId) {
        try {
          const res = await agentic.orchestrate(realTwinId, trimmed);
          const agents = res.steps.filter((s) => s.phase === "synthesize");
          if (agents.length > 0) {
            trace =
              "\n\n🤖 **Agent team at work** — " + agents.length + " agents engaged:\n" +
              agents
                .map((s) => `- ${s.agent.replace("_", " ")}: ${s.detail}`)
                .join("\n");
          }
          answer = res.answer + trace;
        } catch {
          // Fall back to the classic single-agent route.
          if (detectSupplyChain(trimmed)) {
            try {
              const res = await sc.askSupplyChainAgent(trimmed);
              answer = res.answer;
            } catch {
              answer = MOCK_SC_AGENT_RESPONSE.answer;
            }
          } else {
            try {
              const res = await business.askAgent(realTwinId, trimmed);
              answer = res.answer;
            } catch {
              answer = MOCK_AGENT_RESPONSE.answer;
            }
          }
        }
      } else if (detectSupplyChain(trimmed)) {
        try {
          const res = await sc.askSupplyChainAgent(trimmed);
          answer = res.answer;
        } catch {
          answer = MOCK_SC_AGENT_RESPONSE.answer;
        }
      } else {
        answer = MOCK_AGENT_RESPONSE.answer;
      }
      // Typewriter streaming: reveal progressively.
      let revealed = "";
      for (let i = 0; i < answer.length; i += 4) {
        revealed = answer.slice(0, i);
        updateMessage(assistantId, { content: revealed, streaming: true });
        await new Promise((r) => setTimeout(r, 14));
      }
      updateMessage(assistantId, { content: answer, streaming: false });
    } catch (err) {
      updateMessage(assistantId, { content: `⚠️ ${errorMessage(err)}`, streaming: false });
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] flex-col space-y-4">
      <PageHeader
        title="AI Assistant"
        description="Ask the decision engine anything about your business or supply chain"
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setSetupOpen(true)} disabled={setupOpen}>
              <Sparkles /> {setupOpen ? "Setting up…" : "Personalize"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => { clearHistory(); toast.info("Conversation cleared"); }}>
              <Eraser /> Clear history
            </Button>
          </>
        }
      />

      {/* First-time personalisation banner */}
      {setupNeeded && !setupOpen && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-3 rounded-lg border border-primary/25 bg-gradient-to-r from-primary/10 to-violet-500/10 px-4 py-3 sm:flex-row sm:items-center"
        >
          <div className="flex flex-1 items-start gap-2.5">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <Sparkles className="h-3.5 w-3.5" />
            </span>
            <p className="text-sm">
              <b>Make this workspace yours.</b>{" "}
              <span className="text-muted-foreground">
                Tell the assistant about your business and your preferences — the whole platform adapts to you, including your profile.
              </span>
            </p>
          </div>
          <Button size="sm" onClick={() => setSetupOpen(true)} className="shrink-0 gap-2 bg-gradient-to-r from-blue-500 to-violet-600 hover:from-blue-600 hover:to-violet-700">
            Start setup <ArrowUp className="h-3.5 w-3.5 rotate-90" />
          </Button>
        </motion.div>
      )}

      <div className="flex min-h-0 flex-1 flex-col rounded-lg border bg-card">
        {setupOpen ? (
          <OnboardingConversation twin={twins?.[0] ?? null} twinId={realTwinId} onDone={onSetupDone} onCancel={() => setSetupOpen(false)} />
        ) : (
          <>
            {/* Messages */}
            <ScrollArea className="flex-1">
              <div className="space-y-4 p-5">
                {!mounted || messages.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center gap-4 py-16 text-center">
                    <motion.div
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 shadow-xl shadow-primary/20"
                    >
                      <Bot className="h-8 w-8 text-white" />
                    </motion.div>
                    <div>
                      <h2 className="text-lg font-semibold">{greeting}</h2>
                      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
                        {setupNeeded
                          ? "Tell me about your company to personalise this workspace, or jump straight in with a question."
                          : `Ask about pricing, growth strategy, profitability, suppliers or logistics for ${profile.business.name || "your business"}. Responses stream in real time.`}
                      </p>
                    </div>
                    <div className="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
                      {suggested.map((q, i) => (
                        <motion.button
                          key={q}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.05 }}
                          onClick={() => send(q)}
                          className="flex items-center gap-2 rounded-lg border px-3 py-2.5 text-left text-sm transition-colors hover:border-primary/50 hover:bg-primary/5"
                        >
                          <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary" />
                          <span className="line-clamp-1">{q}</span>
                        </motion.button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((m) => (
                    <ChatMessage key={m.id} role={m.role} content={m.content} streaming={m.streaming} />
                  ))
                )}
                <div ref={bottomRef} />
              </div>
            </ScrollArea>

            {/* Composer */}
            <div className="border-t p-3">
              <div className="flex items-end gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send(input);
                    }
                  }}
                  placeholder="Ask about pricing, profit, suppliers, logistics…  (Enter to send, Shift+Enter for new line)"
                  className="min-h-[52px] max-h-40 flex-1 resize-none"
                  rows={2}
                  disabled={busy}
                  aria-label="Chat message"
                />
                <Button onClick={() => send(input)} disabled={busy || !input.trim()} size="icon" className="h-[52px] w-[52px] shrink-0" aria-label="Send message">
                  <ArrowUp className="h-5 w-5" />
                </Button>
              </div>
              <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <User className="h-3 w-3" /> Answers are AI-generated and should be reviewed by a human before major decisions.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
