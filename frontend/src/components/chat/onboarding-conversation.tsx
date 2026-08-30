"use client";

import { useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowUp,
  Building2,
  Check,
  Loader2,
  RefreshCw,
  Rocket,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { ChatMessage } from "@/components/chat/chat-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useProfileStore, type BusinessProfile, type PersonalProfile } from "@/stores/profile-store";
import {
  buildBusinessData,
  businessSummaryMd,
  CHALLENGE_OPTIONS,
  FOCUS_OPTIONS,
  GOAL_OPTIONS,
  INDUSTRY_OPTIONS,
  parseMoney,
  personalSummaryMd,
  RISK_OPTIONS,
  ROLE_OPTIONS,
  SIZE_OPTIONS,
} from "@/lib/personalization";
import * as business from "@/lib/api/business";
import { errorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { DigitalTwin } from "@/lib/types";

/* ── Question flow ────────────────────────────────────────────────────────── */

type QuestionType = "text" | "textOptional" | "money" | "single" | "multi";

interface Question {
  key: string;
  label: string;
  hint?: string;
  type: QuestionType;
  options?: { value: string; label: string }[];
}

const QUESTIONS: Question[] = [
  // ── Business profile ────────────────────────────────────────────────
  {
    key: "b_name",
    label: "Let's start with your company. **What is it called?**",
    hint: "e.g. GreenLeaf Organics",
    type: "text",
  },
  {
    key: "b_industry",
    label: "Great — **which industry are you in?**",
    type: "single",
    options: INDUSTRY_OPTIONS,
  },
  {
    key: "b_employees",
    label: "**How many people work there?**",
    type: "single",
    options: SIZE_OPTIONS.map((o) => ({ value: o.value, label: o.label })),
  },
  {
    key: "b_revenue",
    label: "What is your **approximate annual revenue**?",
    hint: "e.g. $5M, 5 million or 5,000,000",
    type: "money",
  },
  {
    key: "b_challenges",
    label: "What is your **biggest challenge** right now?",
    hint: "Pick one or more — I'll tailor the dashboards to these.",
    type: "multi",
    options: CHALLENGE_OPTIONS,
  },
  {
    key: "b_goals",
    label: "And your **#1 goal for the next 12 months**?",
    hint: "Pick one or more.",
    type: "multi",
    options: GOAL_OPTIONS,
  },
  // ── Personal profile ────────────────────────────────────────────────
  {
    key: "p_name",
    label: "Company locked in. Now about you — **what should I call you?**",
    hint: "Your first name is fine.",
    type: "text",
  },
  {
    key: "p_role",
    label: `Nice to meet you! **What's your role?**`,
    type: "single",
    options: ROLE_OPTIONS,
  },
  {
    key: "p_email",
    label: "What's your **email**? (optional — used for reports & notifications)",
    type: "textOptional",
  },
  {
    key: "p_style",
    label: "How do you like to make decisions?",
    type: "single",
    options: RISK_OPTIONS,
  },
  {
    key: "p_focus",
    label: "Last one — **what should the platform focus on for you?**",
    hint: "Pick one or more.",
    type: "multi",
    options: FOCUS_OPTIONS,
  },
];

const BUSINESS_COUNT = QUESTIONS.filter((q) => q.key.startsWith("b_")).length;

interface HistoryEntry {
  role: "user" | "assistant";
  content: string;
}

const optionLabel = (opts: { value: string; label: string }[] | undefined, v: string) =>
  opts?.find((o) => o.value === v)?.label ?? v;

/* ── Component ────────────────────────────────────────────────────────────── */

interface OnboardingConversationProps {
  twin: DigitalTwin | null;
  /** Real backend twin id (null when demo/offline). */
  twinId: string | null;
  onDone: (opts: { twinUpdated: boolean }) => void;
  onCancel: () => void;
}

export function OnboardingConversation({ twin, twinId, onDone, onCancel }: OnboardingConversationProps) {
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [bus, setBus] = useState<Partial<BusinessProfile>>({});
  const [per, setPer] = useState<Partial<PersonalProfile>>({});
  const [multiSel, setMultiSel] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [applying, setApplying] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const finished = step >= QUESTIONS.length;
  const q = finished ? null : QUESTIONS[step];
  const currentPhase = q?.key.startsWith("b_") ? "business" : "personal";
  const total = QUESTIONS.length;
  const progress = Math.round((Math.min(step, total) / total) * 100);

  /* ── History: intro + answered Q/A pairs ──────────────────────────── */
  const history: HistoryEntry[] = [
    {
      role: "assistant",
      content:
        "I'd love to make this workspace truly **yours**. I'll ask a few quick questions about your company and about you — then the whole platform adapts: dashboards, suggestions, even the profile.\n\nThis takes about a minute. Ready?",
    },
  ];
  for (let i = 0; i < Math.min(step, total); i++) {
    const question = QUESTIONS[i];
    const a = answers[question.key];
    history.push({
      role: "user",
      content: Array.isArray(a) ? a.map((v) => optionLabel(question.options, v)).join(", ") : String(a ?? ""),
    });
    history.push({
      role: "assistant",
      content: question.label + (question.hint ? `\n\n> ${question.hint}` : ""),
    });
  }

  /* ── Answer handlers ───────────────────────────────────────────────── */
  const persistAnswer = (question: Question, value: string | string[]) => {
    setAnswers((prev) => ({ ...prev, [question.key]: value }));
    switch (question.key) {
      case "b_name":
        setBus((b) => ({ ...b, name: String(value) }));
        break;
      case "b_industry": {
        const opt = INDUSTRY_OPTIONS.find((o) => o.value === value);
        setBus((b) => ({ ...b, industry: String(value), industryLabel: opt?.label ?? "" }));
        break;
      }
      case "b_employees": {
        const opt = SIZE_OPTIONS.find((o) => o.value === value);
        setBus((b) => ({ ...b, employees: opt?.employees ?? 0 }));
        break;
      }
      case "b_revenue":
        setBus((b) => ({ ...b, revenue: parseMoney(String(value)) ?? 0 }));
        break;
      case "b_challenges":
        setBus((b) => ({ ...b, challenges: value as string[] }));
        break;
      case "b_goals":
        setBus((b) => ({ ...b, goals: value as string[] }));
        break;
      case "p_name":
        setPer((p) => ({ ...p, name: String(value) }));
        break;
      case "p_role":
        setPer((p) => ({ ...p, role: String(value) }));
        break;
      case "p_email":
        setPer((p) => ({ ...p, email: String(value) }));
        break;
      case "p_style":
        setPer((p) => ({ ...p, decisionStyle: String(value) }));
        break;
      case "p_focus":
        setPer((p) => ({ ...p, focusAreas: value as string[] }));
        break;
    }
  };

  const advance = () => {
    setText("");
    setMultiSel([]);
    setStep((s) => s + 1);
    requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }));
  };

  const answerSingle = (value: string) => {
    if (!q) return;
    persistAnswer(q, value);
    advance();
  };

  const answerMulti = () => {
    if (!q || multiSel.length === 0) return;
    persistAnswer(q, [...multiSel]);
    advance();
  };

  const answerText = () => {
    if (!q) return;
    const value = text.trim();
    if (q.type === "money") {
      const n = parseMoney(value);
      if (n === null || n <= 0) {
        toast.warning("I didn't catch that — try something like 5,000,000 or $5M");
        return;
      }
      persistAnswer(q, value);
      advance();
      return;
    }
    if (value === "") {
      toast.warning(q.type === "textOptional" ? "Leave it blank and press Skip, or type your email." : "Go ahead — type an answer above.");
      return;
    }
    persistAnswer(q, value);
    advance();
  };

  const skipOptional = () => {
    if (!q) return;
    persistAnswer(q, "(skipped)");
    advance();
  };

  const restart = () => {
    setStep(0);
    setAnswers({});
    setBus({});
    setPer({});
    setMultiSel([]);
    setText("");
  };

  /* ── Apply: save profile + update twin ────────────────────────────── */
  const apply = async () => {
    setApplying(true);
    let twinUpdated = false;
    try {
      const store = useProfileStore.getState();
      store.updateBusiness(bus);
      store.updatePersonal(per);
      store.setStatus("complete");

      if (twinId && twin) {
        try {
          await business.updateTwin(twinId, { ...twin, ...buildBusinessData(bus, twin) });
          qc.invalidateQueries({ queryKey: ["twin"] });
          qc.invalidateQueries({ queryKey: ["twins"] });
          twinUpdated = true;
        } catch (err) {
          // Backend unreachable → profile still saved locally.
          console.warn("Twin update skipped:", errorMessage(err));
        }
      }
      toast.success(twinUpdated ? "Workspace personalised — profile & digital twin updated" : "Workspace personalised — profile saved locally");
      onDone({ twinUpdated });
    } catch (err) {
      toast.error(errorMessage(err));
      setApplying(false);
    }
  };

  /* ── Render ───────────────────────────────────────────────────────── */
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Progress header */}
      <div className="flex items-center gap-3 border-b px-4 py-2.5">
        <span
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
            currentPhase === "business" ? "bg-primary/10 text-primary" : "bg-violet-500/10 text-violet-500"
          )}
        >
          {currentPhase === "business" ? <Building2 className="h-4 w-4" /> : <User className="h-4 w-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">              <p className="text-xs font-medium">
                {finished ? "Summary" : currentPhase === "business" ? "Company profile" : "Personal profile"}
                <span className="ml-1.5 text-muted-foreground">
                  · {Math.min(step + 1, total)}/{total}
                </span>
              </p>
            <span className="text-[10px] tabular-nums text-muted-foreground">{progress}%</span>
          </div>
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 via-violet-500 to-fuchsia-500"
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onCancel} aria-label="Close setup">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Conversation */}
      <ScrollArea className="flex-1">
        <div className="space-y-4 p-5">
          {history.map((h, i) => (
            <ChatMessage key={`h-${i}`} role={h.role} content={h.content} />
          ))}

          {/* Current question */}
          {!finished && q && (
            <AnimatePresence mode="wait">
              <motion.div
                key={q.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.22 }}
                className="space-y-3"
              >
                <ChatMessage role="assistant" content={q.label + (q.hint ? `\n\n> ${q.hint}` : "")} />

                {(q.type === "single" || q.type === "multi") && (
                  <div className="ml-11 flex flex-wrap gap-2">
                    {(q.options ?? []).map((opt) => {
                      const selected = q.type === "multi" && multiSel.includes(opt.value);
                      return (
                        <button
                          key={opt.value}
                          onClick={() => {
                            if (q.type === "single") answerSingle(opt.value);
                            else setMultiSel((sel) => (sel.includes(opt.value) ? sel.filter((v) => v !== opt.value) : [...sel, opt.value]));
                          }}
                          className={cn(
                            "group flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm transition-all duration-150",
                            selected
                              ? "border-primary bg-primary/15 text-primary shadow-sm"
                              : "border-border bg-card hover:border-primary/50 hover:bg-primary/5"
                          )}
                        >
                          {q.type === "multi" && (
                            <span
                              className={cn(
                                "flex h-4 w-4 items-center justify-center rounded-full border transition-colors",
                                selected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/40 group-hover:border-primary/50"
                              )}
                            >
                              {selected && <Check className="h-3 w-3" />}
                            </span>
                          )}
                          {opt.label}
                        </button>
                      );
                    })}
                    {q.type === "multi" && (
                      <Button size="sm" className="h-8 rounded-full px-4" onClick={answerMulti} disabled={multiSel.length === 0}>
                        Confirm {multiSel.length > 0 ? `(${multiSel.length})` : ""} <ArrowUp className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {step > 0 && (
                      <button
                        onClick={() => setStep((s) => Math.max(0, s - 1))}
                        className="self-center text-[11px] text-muted-foreground underline-offset-2 hover:underline"
                      >
                        ← Back
                      </button>
                    )}
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          )}

          {/* Summary */}
          {finished && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
              <ChatMessage
                role="assistant"
                content={
                  "Here's what I learned. Review it and I'll personalise your whole workspace — profile, dashboards, suggestions and your digital twin.\n\n### 🏢 Company\n" +
                  businessSummaryMd(bus) +
                  "\n\n### 👤 You\n" +
                  personalSummaryMd(per)
                }
              />
              <div className="ml-11 flex flex-wrap gap-2">
                <Button size="sm" className="gap-2 bg-gradient-to-r from-blue-500 to-violet-600 hover:from-blue-600 hover:to-violet-700" onClick={apply} disabled={applying}>
                  {applying ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
                  {applying ? "Personalising…" : "Apply & personalise workspace"}
                </Button>
                <Button size="sm" variant="outline" className="gap-2" onClick={restart} disabled={applying}>
                  <RefreshCw className="h-4 w-4" /> Start over
                </Button>
                <Button size="sm" variant="ghost" className="gap-2" onClick={onCancel} disabled={applying}>
                  <X className="h-4 w-4" /> Cancel
                </Button>
              </div>
              {applying && (
                <p className="ml-11 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Sparkles className="h-3.5 w-3.5 text-primary" /> Saving your profile
                  {twinId ? " and updating your digital twin…" : " — connect the backend to also update your digital twin…"}
                </p>
              )}
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Text composer (only for text-style steps) */}
      {!finished && q && (q.type === "text" || q.type === "textOptional" || q.type === "money") && (
        <div className="border-t p-3">
          <div className="flex items-end gap-2">
            <Input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  answerText();
                }
              }}
              placeholder={q.type === "money" ? "e.g. 5,000,000 or $5M" : q.type === "textOptional" ? "you@company.com" : q.type === "text" && q.key === "p_name" ? "Your first name" : "Type your answer…"}
              className="min-h-[44px] flex-1"
              autoFocus
              aria-label="Answer"
            />
            <Button onClick={answerText} size="icon" className="h-[44px] w-[44px] shrink-0" aria-label="Send answer">
              <ArrowUp className="h-5 w-5" />
            </Button>
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            {q.type === "textOptional" && (
              <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-muted-foreground" onClick={skipOptional}>
                Skip
              </Button>
            )}
            <p className="text-[11px] text-muted-foreground">
              {q.key === "b_name" ? "Press Enter to continue" : q.type === "money" ? "Any format works — I'll interpret it" : ""}
            </p>
            {step > 0 && (
              <button onClick={() => setStep((s) => Math.max(0, s - 1))} className="ml-auto text-[11px] text-muted-foreground underline-offset-2 hover:underline">
                ← Back
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
