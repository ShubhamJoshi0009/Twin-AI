"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  DollarSign,
  Globe2,
  LineChart,
  Loader2,
  MapPin,
  Network,
  Play,
  Radar,
  RefreshCw,
  Sparkles,
  Terminal,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTwins } from "@/hooks/use-api";
import * as agentic from "@/lib/api/agentic";
import { errorMessage } from "@/lib/api/client";
import { useMounted } from "@/hooks/use-mounted";
import { cn } from "@/lib/utils";
import type { AgentStep, OrchestrationResponse } from "@/lib/types";

const AGENT_META: Record<string, { label: string; icon: typeof Bot; color: string; dot: string }> = {
  orchestrator: { label: "Orchestrator", icon: BrainCircuit, color: "text-violet-500", dot: "bg-violet-500" },
  financial: { label: "Financial Analyst", icon: DollarSign, color: "text-sky-500", dot: "bg-sky-500" },
  market: { label: "Market Intelligence", icon: Globe2, color: "text-emerald-500", dot: "bg-emerald-500" },
  supply_chain: { label: "Supply Chain Analyst", icon: Network, color: "text-amber-500", dot: "bg-amber-500" },
  strategy: { label: "Strategy Advisor", icon: LineChart, color: "text-rose-500", dot: "bg-rose-500" },
};

const PHASE_BADGE: Record<string, { label: string; cls: string }> = {
  plan: { label: "Plan", cls: "bg-sky-500/10 text-sky-500 border-sky-500/30" },
  tool_call: { label: "Tool", cls: "bg-violet-500/10 text-violet-500 border-violet-500/30" },
  observe: { label: "Observe", cls: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30" },
  synthesize: { label: "Synthesize", cls: "bg-amber-500/10 text-amber-500 border-amber-500/30" },
  reflect: { label: "Reflect", cls: "bg-rose-500/10 text-rose-500 border-rose-500/30" },
};

const PRESETS = [
  "Complete business assessment",
  "What are my biggest risks right now?",
  "Should I expand or cut costs first?",
  "How exposed am I to shipping disruptions?",
];

export default function CommandCenterPage() {
  const { data: twins } = useTwins();
  const twinId = twins?.[0]?.id ?? null;
  const mounted = useMounted();
  const [question, setQuestion] = useState(PRESETS[0]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<OrchestrationResponse | null>(null);
  const [visibleSteps, setVisibleSteps] = useState(0);
  const traceRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reveal reasoning steps progressively for the live "agent at work" effect.
  // Keyed off `result` alone: `setResult(res)` and `setRunning(false)` are
  // batched into one render, so requiring `running` here would skip the reveal.
  useEffect(() => {
    if (!result) return;
    setVisibleSteps(0);
    timerRef.current = setInterval(() => {
      setVisibleSteps((v) => {
        if (v >= (result.steps.length ?? 0)) {
          if (timerRef.current) clearInterval(timerRef.current);
          return v;
        }
        return v + 1;
      });
    }, 180);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [result]);

  useEffect(() => {
    if (visibleSteps > 0) traceRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [visibleSteps]);

  const run = async (q: string) => {
    if (!twinId) {
      toast.error("No digital twin found — create one first via the onboarding wizard.");
      return;
    }
    setQuestion(q);
    setResult(null);
    setVisibleSteps(0);
    setRunning(true);
    try {
      const res = await agentic.orchestrate(twinId, q);
      setResult(res);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRunning(false);
    }
  };

  const done = !!result && visibleSteps >= result.steps.length;
  // While steps are still revealing (or the request is in flight), the agent
  // of the latest visible step is shown as "working".
  const revealing = !!result && !done;
  const activeAgent = result?.steps[Math.max(0, Math.min(visibleSteps, (result.steps.length ?? 1) - 1))]?.agent;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agentic Command Center"
        description="Four specialized AI agents inspect your business, pull live news, and collaborate on a recommendation — watch every step"
        actions={
          <Badge variant="secondary" className="gap-1.5 font-mono text-[11px]">
            <Cpu className="h-3 w-3" /> {twinId ? "Agents: 4" : "No twin"}
          </Badge>
        }
      />

      {/* Agent strip */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Object.entries(AGENT_META).filter(([k]) => k !== "orchestrator").map(([key, meta]) => {
          const Icon = meta.icon;
          const active = (running || revealing) && activeAgent === key;
          const finished = result && !revealing && result.steps.some((s) => s.agent === key);
          return (
            <motion.div
              key={key}
              animate={active ? { scale: 1.02 } : { scale: 1 }}
              className={cn(
                "flex items-center gap-3 rounded-lg border bg-card p-3 transition-colors",
                active ? "border-primary/50 shadow-lg shadow-primary/10" : "border-border"
              )}
            >
              <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg bg-muted", meta.color)}>
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{meta.label}</p>
                <p className="text-[11px] text-muted-foreground">
                  {active ? (
                    <span className="inline-flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> working…</span>
                  ) : finished ? (
                    <span className="inline-flex items-center gap-1 text-success"><CheckCircle2 className="h-3 w-3" /> done</span>
                  ) : running || revealing ? (
                    "queued"
                  ) : (
                    "standby"
                  )}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Composer */}
      <Card>
        <CardContent className="space-y-3 pt-5">
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={2}
            placeholder="Ask the agent team anything about your business…"
            className="resize-none"
            aria-label="Question for the agent team"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  onClick={() => setQuestion(p)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-[11px] transition-colors",
                    question === p ? "border-primary/60 bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/40"
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
            <Button onClick={() => run(question)} disabled={running || !question.trim()}>
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {running ? "Agents working…" : "Deploy agent team"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <div className="grid gap-4 xl:grid-cols-3">
          {/* Reasoning trace */}
          <Card className="xl:col-span-2">
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm">Reasoning Trace</CardTitle>
              </div>
              <Badge variant="secondary" className="font-mono text-[10px]">
                {done ? `${result.steps.length} steps · ${result.mode === "llm" ? "LLM" : "rule+news"}` : "live"}
              </Badge>
            </CardHeader>
            <CardContent>
              <div ref={traceRef} className="relative space-y-2 pl-5 before:absolute before:left-[7px] before:top-1 before:bottom-1 before:w-px before:bg-border">
                {result.steps.slice(0, visibleSteps).map((s, i) => {
                  const meta = AGENT_META[s.agent] ?? AGENT_META.orchestrator;
                  const phase = PHASE_BADGE[s.phase] ?? PHASE_BADGE.plan;
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="relative"
                    >
                      <span className={cn("absolute -left-5 top-2.5 h-3 w-3 rounded-full border-2 border-card", meta.dot)} />
                      <div className="flex flex-wrap items-center gap-1.5 text-xs">
                        <span className={cn("font-medium", meta.color)}>{meta.label}</span>
                        <span className={cn("rounded border px-1.5 py-px text-[10px] font-medium", phase.cls)}>{phase.label}</span>
                        {s.tool && <span className="font-mono text-muted-foreground">↳ {s.tool}</span>}
                        {typeof s.duration_ms === "number" && s.duration_ms > 0 && (
                          <span className="font-mono text-[10px] text-muted-foreground/70">{s.duration_ms}ms</span>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">{s.detail}</p>
                    </motion.div>
                  );
                })}
                {running && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                    Orchestrator delegating to next agent…
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Verdict */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-chart-3" />
                <CardTitle className="text-sm">Agent Verdict</CardTitle>
              </div>
              <CardDescription className="text-xs">Confidence {result.confidence}% · {result.mode === "llm" ? "LLM-synthesized" : "news + rules"}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <AnimatePresence mode="wait">
                <motion.div
                  key={done ? "done" : "pending"}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="rounded-lg border border-primary/20 bg-primary/5 p-3"
                >
                  <p className="text-sm font-semibold leading-snug">{done ? result.recommendation : "Agents are still working…"}</p>
                </motion.div>
              </AnimatePresence>
              {done && (
                <div className="space-y-3">
                  <div className="rounded-md bg-muted/60 p-3">
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Top recommendation</p>
                    <p className="mt-0.5 text-sm font-medium">{result.recommendation}</p>
                  </div>

                  {/* Live chokepoint risks the strategy agent is citing */}
                  {(result.chokepoint_risks ?? []).length > 0 && (
                    <div className="rounded-md border border-amber-500/25 bg-amber-500/5 p-3">
                      <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
                        <Radar className="h-3 w-3" /> Live route risks cited
                      </p>
                      <div className="space-y-1.5">
                        {(result.chokepoint_risks ?? []).slice(0, 3).map((r) => (
                          <div key={r.chokepoint_id} className="flex items-center gap-2 text-xs">
                            <MapPin className="h-3 w-3 shrink-0 text-amber-500" />
                            <span className="min-w-0 flex-1 truncate font-medium">{r.chokepoint}</span>
                            <span className="text-muted-foreground">{r.event}</span>
                            <Badge
                              variant={r.severity === "critical" ? "destructive" : r.severity === "high" ? "warning" : "secondary"}
                              className="shrink-0 !px-1.5 !text-[9px] font-mono"
                            >
                              {r.risk_score}/100
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="secondary">Market: {result.market_context}</Badge>
                    <Badge variant="secondary">{result.news.length} headlines</Badge>
                  </div>
                  <Button variant="outline" size="sm" className="w-full" onClick={() => run(question)}>
                    <RefreshCw className="h-3.5 w-3.5" /> Re-run analysis
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {!result && !running && mounted && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
            <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-blue-600 shadow-xl shadow-primary/20">
              <Bot className="h-7 w-7 text-white" />
            </motion.div>
            <div>
              <p className="font-semibold">Four agents. One command.</p>
              <p className="mx-auto max-w-md text-sm text-muted-foreground">
                The Financial Analyst, Market Intelligence, Supply Chain Analyst and Strategy Advisor inspect live data, run tools, and stream their reasoning to you — fully transparent, step by step.
              </p>
            </div>
            <Button size="sm" onClick={() => run(question)}>
              <ArrowRight className="h-4 w-4" /> Run the demo analysis
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
