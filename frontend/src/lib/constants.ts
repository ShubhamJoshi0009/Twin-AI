import type { DecisionTypeInfo, Severity } from "./types";

/* ── Application meta ─────────────────────────────────────────────────────── */

export const APP_NAME = "Business Twin AI";
export const APP_TAGLINE = "Enterprise Digital Twin & Supply Chain Intelligence";
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/* ── Navigation ───────────────────────────────────────────────────────────── */

export interface NavItem {
  title: string;
  href: string;
  icon: string;
  section: "Overview" | "Decision Intelligence" | "Supply Chain" | "System";
  badge?: number;
}

export const NAV_ITEMS: NavItem[] = [
  { title: "Dashboard", href: "/dashboard", icon: "LayoutDashboard", section: "Overview" },
  { title: "Digital Twin", href: "/digital-twin", icon: "Network", section: "Overview" },
  { title: "Command Center", href: "/command-center", icon: "Bot", section: "Decision Intelligence" },
  { title: "Scenario Simulator", href: "/simulator", icon: "FlaskConical", section: "Decision Intelligence" },
  { title: "Business Insights", href: "/insights", icon: "Lightbulb", section: "Decision Intelligence" },
  { title: "AI Assistant", href: "/chat", icon: "MessagesSquare", section: "Decision Intelligence" },
  { title: "Market Watch", href: "/market-watch", icon: "CandlestickChart", section: "Supply Chain" },
  { title: "Supply Chain", href: "/supply-chain", icon: "Boxes", section: "Supply Chain" },
  { title: "SC Scenario Simulator", href: "/sc-simulator", icon: "Siren", section: "Supply Chain" },
  { title: "Route Diversion", href: "/route-diversion", icon: "Map", section: "Supply Chain" },
  { title: "Suppliers", href: "/suppliers", icon: "Truck", section: "Supply Chain" },
  { title: "Inventory", href: "/inventory", icon: "PackageSearch", section: "Supply Chain" },
  { title: "Logistics", href: "/logistics", icon: "Ship", section: "Supply Chain" },
  { title: "Reports", href: "/reports", icon: "FileText", section: "System" },
  { title: "Timeline", href: "/timeline", icon: "History", section: "System" },
  { title: "Settings", href: "/settings", icon: "Settings", section: "System" },
];

export const BREADCRUMB_OVERRIDES: Record<string, string> = {
  dashboard: "Dashboard",
  "digital-twin": "Digital Twin",
  "command-center": "Command Center",
  "market-watch": "Market Watch",
  simulator: "Scenario Simulator",
  "route-diversion": "Route Diversion",
  "sc-simulator": "SC Scenario Simulator",
  insights: "Business Insights",
  chat: "AI Assistant",
  "supply-chain": "Supply Chain",
  suppliers: "Suppliers",
  inventory: "Inventory",
  logistics: "Logistics",
  alerts: "Alerts Center",
  reports: "Reports",
  timeline: "Timeline",
  settings: "Settings",
};

/* ── Decision types (mirrors backend) ─────────────────────────────────────── */

export const DECISION_TYPES: DecisionTypeInfo[] = [
  {
    value: "increase_price",
    label: "Increase Price",
    description: "Raise product pricing by a percentage",
    icon: "TrendingUp",
    params: [{ key: "percent", label: "Increase %", type: "number", default: 10, min: 1, max: 100 }],
  },
  {
    value: "reduce_price",
    label: "Reduce Price",
    description: "Lower product pricing to win demand",
    icon: "TrendingDown",
    params: [{ key: "percent", label: "Reduce %", type: "number", default: 10, min: 1, max: 50 }],
  },
  {
    value: "open_branch",
    label: "Open Branch",
    description: "Open a new branch / office",
    icon: "Store",
    params: [{ key: "city", label: "City", type: "text", default: "Austin" }],
  },
  {
    value: "close_branch",
    label: "Close Branch",
    description: "Close an under-performing branch",
    icon: "XCircle",
    params: [{ key: "city", label: "City", type: "text", default: "Detroit" }],
  },
  {
    value: "hire_employees",
    label: "Hire Employees",
    description: "Add headcount to a department",
    icon: "UserPlus",
    params: [
      { key: "count", label: "Count", type: "number", default: 5, min: 1, max: 500 },
      { key: "department", label: "Department", type: "select", default: "operations", options: [
        { value: "operations", label: "Operations" },
        { value: "sales", label: "Sales" },
        { value: "marketing", label: "Marketing" },
        { value: "support", label: "Support" },
      ] },
    ],
  },
  {
    value: "layoff_employees",
    label: "Reduce Workforce",
    description: "Reduce headcount to cut costs",
    icon: "UserMinus",
    params: [{ key: "count", label: "Count", type: "number", default: 5, min: 1, max: 500 }],
  },
  {
    value: "increase_marketing",
    label: "Increase Marketing",
    description: "Boost marketing budget to drive growth",
    icon: "Megaphone",
    params: [
      { key: "percent", label: "Increase %", type: "number", default: 20, min: 1, max: 200 },
      { key: "channel", label: "Channel", type: "select", default: "digital", options: [
        { value: "digital", label: "Digital" },
        { value: "tv", label: "TV" },
        { value: "print", label: "Print" },
        { value: "events", label: "Events" },
      ] },
    ],
  },
  {
    value: "reduce_marketing",
    label: "Reduce Marketing",
    description: "Cut marketing spend to preserve cash",
    icon: "MegaphoneOff",
    params: [{ key: "percent", label: "Reduce %", type: "number", default: 15, min: 1, max: 100 }],
  },
  {
    value: "launch_product",
    label: "Launch Product",
    description: "Introduce a new product to market",
    icon: "Rocket",
    params: [
      { key: "product_name", label: "Product name", type: "text", default: "Apex Widget" },
      { key: "price", label: "Price ($)", type: "number", default: 99, min: 1 },
    ],
  },
  {
    value: "stop_product",
    label: "Discontinue Product",
    description: "Retire a product from the catalogue",
    icon: "PackageX",
    params: [{ key: "product_name", label: "Product name", type: "text", default: "Legacy Widget" }],
  },
  {
    value: "enter_new_city",
    label: "Enter New Market",
    description: "Expand into a new city / market",
    icon: "MapPin",
    params: [
      { key: "city", label: "City", type: "text", default: "Denver" },
      { key: "investment", label: "Investment ($)", type: "number", default: 250000, min: 10000 },
    ],
  },
  {
    value: "change_supplier_cost",
    label: "Change Supplier Cost",
    description: "Renegotiate supplier pricing",
    icon: "Handshake",
    params: [{ key: "percent", label: "Cost change %", type: "number", default: -5, min: -50, max: 50 }],
  },
  {
    value: "increase_production_capacity",
    label: "Increase Production",
    description: "Expand production capacity",
    icon: "Factory",
    params: [{ key: "percent", label: "Increase %", type: "number", default: 20, min: 1, max: 200 }],
  },
];

export const DECISION_TYPE_MAP = Object.fromEntries(DECISION_TYPES.map((d) => [d.value, d]));

/* ── Severity / priority themes ───────────────────────────────────────────── */

export const SEVERITY_THEME: Record<Severity, { label: string; text: string; bg: string; border: string; dot: string }> = {
  critical: {
    label: "Critical",
    text: "text-red-500",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    dot: "bg-red-500",
  },
  high: {
    label: "High",
    text: "text-orange-500",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    dot: "bg-orange-500",
  },
  medium: {
    label: "Medium",
    text: "text-amber-500",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    dot: "bg-amber-500",
  },
  low: {
    label: "Low",
    text: "text-sky-500",
    bg: "bg-sky-500/10",
    border: "border-sky-500/30",
    dot: "bg-sky-500",
  },
  warning: {
    label: "Warning",
    text: "text-amber-500",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    dot: "bg-amber-500",
  },
  info: {
    label: "Info",
    text: "text-slate-500 dark:text-slate-400",
    bg: "bg-slate-500/10",
    border: "border-slate-500/30",
    dot: "bg-slate-400",
  },
};

/* ── Chart palette ────────────────────────────────────────────────────────── */

export const CHART_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

export const HEALTH_COLORS = {
  good: "hsl(var(--success))",
  warning: "hsl(var(--warning))",
  critical: "hsl(var(--destructive))",
};

/* ── Suggested questions for the AI chat ──────────────────────────────────── */

export const SUGGESTED_QUESTIONS = [
  "Should we increase prices?",
  "How can we improve profit?",
  "Which supplier is most risky?",
  "Generate a growth strategy",
  "Where should we cut costs first?",
  "Should we expand into a new market?",
];
