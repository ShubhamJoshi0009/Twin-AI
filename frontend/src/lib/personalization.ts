import type { BusinessData } from "./types";
import type { BusinessProfile, PersonalProfile } from "@/stores/profile-store";

/* ─────────────────────────────────────────────────────────────────────────────
 * Personalization helpers — shared by the AI-assistant setup conversation,
 * the chat greeting, suggested questions and the twin update payload.
 * ───────────────────────────────────────────────────────────────────────────── */

/* ── Answer options shown as quick-reply chips ────────────────────────────── */

export interface Option {
  value: string;
  label: string;
}

export const INDUSTRY_OPTIONS: Option[] = [
  { value: "technology", label: "Technology / SaaS" },
  { value: "retail", label: "Retail & E-commerce" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "food_retail", label: "Food & Grocery" },
  { value: "healthcare", label: "Healthcare" },
  { value: "finance", label: "Finance" },
  { value: "logistics", label: "Logistics & Supply Chain" },
  { value: "energy", label: "Energy" },
  { value: "education", label: "Education" },
  { value: "real_estate", label: "Real Estate" },
  { value: "other", label: "Other" },
];

export const SIZE_OPTIONS: { value: string; label: string; employees: number }[] = [
  { value: "1-10", label: "1–10 people", employees: 6 },
  { value: "11-50", label: "11–50 people", employees: 30 },
  { value: "51-200", label: "51–200 people", employees: 120 },
  { value: "201-1000", label: "201–1,000 people", employees: 500 },
  { value: "1000+", label: "1,000+ people", employees: 2500 },
];

export const CHALLENGE_OPTIONS: Option[] = [
  { value: "revenue", label: "Growing revenue" },
  { value: "cost", label: "Cutting costs" },
  { value: "margin", label: "Improving margins" },
  { value: "supply", label: "Supply chain reliability" },
  { value: "talent", label: "Hiring & retaining talent" },
  { value: "market", label: "Entering new markets" },
  { value: "cash", label: "Cash flow management" },
];

export const GOAL_OPTIONS: Option[] = [
  { value: "profit", label: "Boost profit" },
  { value: "growth", label: "Grow revenue 2×" },
  { value: "expansion", label: "Expand to new markets" },
  { value: "efficiency", label: "Run leaner operations" },
  { value: "risk", label: "Build resilience" },
  { value: "product", label: "Launch new products" },
];

export const ROLE_OPTIONS: Option[] = [
  { value: "founder", label: "Founder / CEO" },
  { value: "operations", label: "Operations" },
  { value: "finance", label: "Finance" },
  { value: "marketing", label: "Marketing / Sales" },
  { value: "supply_chain", label: "Supply Chain" },
  { value: "other", label: "Other" },
];

export const RISK_OPTIONS: Option[] = [
  { value: "conservative", label: "Conservative — protect what we have" },
  { value: "balanced", label: "Balanced — steady, measured growth" },
  { value: "aggressive", label: "Aggressive — go big, move fast" },
];

export const FOCUS_OPTIONS: Option[] = [
  { value: "profit", label: "Profit & cash flow" },
  { value: "growth", label: "Growth & expansion" },
  { value: "efficiency", label: "Efficiency & cost cutting" },
  { value: "risk", label: "Risk & resilience" },
  { value: "market", label: "Market intelligence" },
];

/* ── Parsing free-text answers ────────────────────────────────────────────── */

/** Parse "5,000,000", "$5M", "5 million", "€2.5m" … → number | null */
export function parseMoney(text: string): number | null {
  const t = text.trim();
  if (!t) return null;
  const digits = t.replace(/[$€£₹]/g, "").replace(/,/g, "");
  if (/^\d+(\.\d+)?$/.test(digits)) {
    const n = parseFloat(digits);
    return Number.isFinite(n) ? Math.round(n) : null;
  }
  const match = digits.toLowerCase().match(/([\d.]+)\s*(b|billion|m|million|k|thousand)/);
  if (!match) return null;
  const num = parseFloat(match[1]);
  if (Number.isNaN(num)) return null;
  const suffix = match[2];
  const mult = suffix.startsWith("b") ? 1_000_000_000 : suffix.startsWith("m") ? 1_000_000 : suffix.startsWith("k") ? 1_000 : 1;
  return Math.round(num * mult);
}

/* ── Twin payload ─────────────────────────────────────────────────────────── */

/** Build a full BusinessData from the collected profile, filling gaps from the existing twin. */
export function buildBusinessData(
  b: Partial<BusinessProfile>,
  existing: Partial<BusinessData> | null = null
): BusinessData {
  const revenue = b.revenue ?? existing?.revenue ?? 1_000_000;
  const expenses = existing?.expenses ?? Math.round(revenue * 0.7);
  return {
    name: (b.name || existing?.name || "My Company").trim(),
    industry: b.industry || existing?.industry || "general",
    description: b.description || existing?.description || null,
    revenue,
    expenses,
    profit: existing?.profit ?? revenue - expenses,
    cash_flow: existing?.cash_flow ?? Math.round(revenue * 0.15),
    customers: existing?.customers ?? Math.max(10, Math.round(revenue / 4000)),
    employees: b.employees || existing?.employees || 60,
    sales: existing?.sales ?? revenue,
    marketing_budget: existing?.marketing_budget ?? Math.round(revenue * 0.08),
    market_share: existing?.market_share ?? 3,
    kpis: existing?.kpis ?? {
      revenue_growth: 10,
      churn_rate: 5,
      customer_lifetime_value: 1500,
      nps_score: 40,
    },
  };
}

/* ── Greeting & questions ─────────────────────────────────────────────────── */

export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name;
}

/** Suggested questions that adapt to the collected industry, goals and focus areas. */
export function personalizedQuestions(
  business: Partial<BusinessProfile>,
  personal: Partial<PersonalProfile>
): string[] {
  const focus = new Set<string>([...(business.priorities ?? []), ...(personal.focusAreas ?? [])]);
  const industry = business.industry ?? "";
  const qs: string[] = [];

  if (focus.has("profit") || focus.has("margin") || focus.has("cost") || focus.has("efficiency") || focus.has("cash")) {
    qs.push("Where should we cut costs first?");
  }
  if (focus.has("growth") || focus.has("expansion") || focus.has("market")) {
    qs.push("Should we expand into a new market?");
  }
  if (focus.has("risk")) {
    qs.push("What are our biggest risks right now?");
  }
  if (focus.has("market")) {
    qs.push("Summarise the latest market news for our industry");
  }
  if (industry === "retail" || industry === "food_retail") {
    qs.push("How can we improve customer retention?");
  } else if (industry === "technology") {
    qs.push("Should we increase prices?");
  } else if (industry === "manufacturing" || industry === "logistics") {
    qs.push("Which supplier is most risky?");
  } else if (industry === "healthcare" || industry === "finance") {
    qs.push("How can we improve profit margins?");
  }

  // Always round out with general questions.
  qs.push("How can we improve profit?", "Generate a growth strategy");
  return [...new Set(qs)].slice(0, 6);
}

/* ── Summary markdown (shown in chat + settings) ──────────────────────────── */

const fmtMoney = (n: number | undefined) =>
  n ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n) : "—";

const fmtList = (xs: string[] | undefined, opts: Option[] = []) => {
  if (!xs || xs.length === 0) return "—";
  return xs.map((v) => opts.find((o) => o.value === v)?.label ?? v).join(", ");
};

export function businessSummaryMd(b: Partial<BusinessProfile>): string {
  const lines = [
    `**${b.name?.trim() || "Your company"}**`,
    `- **Industry:** ${b.industryLabel || b.industry || "—"}`,
    `- **Team size:** ${b.employees ? `${b.employees} people` : "—"}`,
    `- **Annual revenue:** ${fmtMoney(b.revenue)}`,
    `- **Top challenges:** ${fmtList(b.challenges, CHALLENGE_OPTIONS)}`,
    `- **12-month goals:** ${fmtList(b.goals, GOAL_OPTIONS)}`,
  ];
  return lines.join("\n");
}

export function personalSummaryMd(p: Partial<PersonalProfile>): string {
  const lines = [
    `**${p.name?.trim() || "You"}**${p.role ? ` — ${fmtList([p.role], ROLE_OPTIONS)}` : ""}`,
    p.email ? `- **Email:** ${p.email}` : "",
    `- **Decision style:** ${fmtList([p.decisionStyle ?? ""], RISK_OPTIONS)}`,
    `- **Platform focus:** ${fmtList(p.focusAreas, FOCUS_OPTIONS)}`,
  ].filter(Boolean);
  return lines.join("\n");
}
