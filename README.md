# Business Twin AI — Enterprise Digital Twin & Decision Intelligence Platform

> AI-powered decision engine that creates a digital representation of a business, simulates decisions, predicts outcomes, explains predictions, and recommends the best strategy.

## 🏗️ Architecture Overview

```
business_twin_ai/
├── app.py                          # FastAPI application entry point
├── config.py                       # Settings (env vars, Pydantic)
├── database.py                     # Async SQLAlchemy engine & session
├── seed.py                         # Demo-data seeder (auto-runs on empty DB)
├── sample_data.py                  # Sample business dataset
├── core/
│   ├── engines/                    # Business logic engines
│   │   ├── digital_twin.py         # Digital twin CRUD & state management
│   │   ├── simulator.py            # Decision simulation pipeline
│   │   ├── health.py               # Business health scoring
│   │   ├── whatif.py               # What-if scenario comparison
│   │   ├── strategy.py             # Strategy generation
│   │   ├── agent.py                # LLM-powered Q&A agent
│   │   ├── insights.py             # Auto business insights
│   │   └── report.py               # PDF report generation
│   ├── models/
│   │   └── database.py             # SQLAlchemy ORM models
│   └── schemas/
│       └── schemas.py              # Pydantic request/response schemas
├── services/
│   ├── llm/
│   │   └── client.py               # Modular LLM client (OpenAI / Gemini / Fallback)
│   └── prompts/
│       └── templates.py            # All AI prompt templates
└── api/
    └── routes/
        ├── digital_twin.py         # /api/v1/digital-twins
        ├── simulation.py           # /api/v1/simulations
        ├── health.py               # /api/v1/health
        ├── strategy.py             # /api/v1/strategies
        ├── agent.py                # /api/v1/agent
        ├── insights.py             # /api/v1/insights
        ├── report.py               # /api/v1/reports
        └── timeline.py             # /api/v1/timeline
```

## 🚀 Quick Start

### Option 1: Local Development (Recommended)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL and optionally LLM keys

# Start PostgreSQL (or use SQLite for quick testing)
# For SQLite, change DATABASE_URL to:
# DATABASE_URL=sqlite+aiosqlite:///./business_twin.db

# Run the API server
uvicorn business_twin_ai.app:app --reload --host 0.0.0.0 --port 8000

# In a second terminal, run the frontend
cd frontend
npm install
npm run dev   # http://localhost:3000
```

On first startup the API automatically seeds a complete demo dataset (see
[Demo data](#-demo-data--customisation)) so every screen is populated immediately.

- Frontend: http://localhost:3000
- API available at: http://localhost:8000
- Swagger docs: http://localhost:8000/docs

> 💡 Swagger docs (`/docs`) are only exposed when `APP_DEBUG=true` (development).
> In production (`APP_DEBUG=false`) the docs and `/openapi.json` are hidden.

### Option 2: Run Tests

```bash
pip install pytest pytest-asyncio aiosqlite
pytest tests/ -v
```

## 🌍 Going Live (Production)

### Deployment

The app is a standard two-process stack — **FastAPI** (API, port 8000) and
**Next.js standalone** (frontend, port 3000) — with **Postgres** for storage.
There is no Docker, so deploy however you prefer:

- **PaaS** (Render, Railway, Fly.io, etc.): point each service at its start
  command and set the env vars below.
- **VPS / bare metal**: run `uvicorn` and `next start` under a process manager
  (systemd, pm2), and put nginx/Caddy in front for TLS.

### Env vars to set (never commit `.env`)

| Var | Required in prod? | Notes |
|-----|-------------------|-------|
| `DATABASE_URL` | ✅ | Point at your managed/remote Postgres |
| `SECRET_KEY` | ✅ | `openssl rand -hex 32` — if unset, the app generates one per process |
| `CORS_ORIGINS` | ✅ | JSON array of your frontend origin(s) |
| `NEXT_PUBLIC_API_URL` | ✅ | Inlined into the frontend bundle **at build time** — must be the public API URL browsers can reach (e.g. `https://api.yourdomain.com/api/v1`); rebuild the frontend when it changes |
| `APP_DEBUG` | ✅ | `false` (hides Swagger docs, disables SQL echo) |
| `ENABLE_SEED_API` | ✅ | `false` — keep the destructive seed endpoint off |
| `AUTO_SEED_DEMO` | — | `false` once you manage real data |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | — | Live LLM features; rule-based fallbacks work without them |
| `NEWS_API_KEY` | — | Optional NewsAPI.org key |
| `TRUSTED_HOSTS` | — | Comma-separated allowed Host headers (e.g. `api.yourdomain.com`) to block Host-header attacks |

### Production checklist

- [ ] Run the API and frontend behind a TLS reverse proxy (Caddy, Traefik,
      nginx) that terminates HTTPS and forwards `:443 → :3000` (web) and
      `/api → :8000` (API).
- [ ] Set `TRUSTED_HOSTS` to the API's public hostname to block Host-header
      attacks; set `CORS_ORIGINS` to the exact frontend origin.
- [ ] Set `SECRET_KEY` to a long random value and rotate DB credentials.
      If it is left unset the app generates one per process and logs a warning.
- [ ] Keep `ENABLE_SEED_API=false` unless you deliberately expose the
      destructive seed endpoint behind your own auth.
- [ ] Use a managed Postgres with automated backups.
- [ ] Add a real LLM key (`OPENAI_API_KEY` / `GEMINI_API_KEY`) — the app
      works without one via rule-based fallbacks, but the AI features are
      far stronger with a live model.
- [ ] The repo runs CI (`.github/workflows/ci.yml`) — backend `pytest` +
      `ruff`, frontend `tsc` + `next build` — on every push/PR.

## 🧪 Demo Data & Customisation

Out of the box the database is empty, so the app seeds a **demo dataset** on
first startup (`AUTO_SEED_DEMO=true` in `.env`): a digital twin, simulation
history, insights, suppliers, warehouses, inventory and shipments.

```bash
# Seed the demo data (only runs when the DB is empty)
python -m business_twin_ai.seed

# Wipe demo data and reseed from scratch
python -m business_twin_ai.seed --force

# Seed with YOUR OWN business / supply chain profile
python -m business_twin_ai.seed --file ./my-business.json
```

To use your own data instead of the demo dataset, copy `demo_data.example.json`
to e.g. `my-business.json`, fill in your numbers, and either:

- run `python -m business_twin_ai.seed --file ./my-business.json`, or
- set `CUSTOM_DATA_FILE=./my-business.json` in `.env` (used automatically on
  startup).

The custom file format is a JSON object with optional `business`, `simulations`
and `supply_chain` sections (see the example file for the full schema). The
`business` section follows the `BusinessData` API schema; supply chain entries
follow the sample data in `business_twin_ai/supply_chain/sample_data.py`.

### Upload data from the UI

The **Settings → Data & Seeding** section lets you do all of this from the
dashboard: drag & drop a JSON file, preview its contents, apply it to the
database (with a replace-confirmation when data already exists), restore the
demo dataset, or download a fresh template. Backed by these endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/system/seed/status` | Is the database empty or seeded? |
| `POST` | `/api/v1/system/seed` | Apply a custom payload or the demo dataset (`force` to replace) |
| `GET` | `/api/v1/system/seed/template` | Download `demo_data.example.json` |

> ⚠️ `POST /api/v1/system/seed` with `force=true` **replaces all existing data**
> (twins, simulations, insights and supply chain records). The endpoint is
> enabled by default for demos; set `ENABLE_SEED_API=false` in `.env` to disable
> it in production.

> Set `AUTO_SEED_DEMO=false` once you start managing real data — seeding only
> ever runs against an empty database, so it is safe to leave enabled.

## 📡 API Endpoints

### Digital Twin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/digital-twins` | Create a new digital twin |
| `GET` | `/api/v1/digital-twins` | List all digital twins |
| `GET` | `/api/v1/digital-twins/{id}` | Get a digital twin |
| `PUT` | `/api/v1/digital-twins/{id}` | Update business data |
| `DELETE` | `/api/v1/digital-twins/{id}` | Delete a digital twin |

### Simulation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/simulations/{twin_id}/run` | Run a decision simulation |
| `POST` | `/api/v1/simulations/{twin_id}/compare` | Compare multiple scenarios (What-If) |
| `GET` | `/api/v1/simulations/decision-types` | List all decision types |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health/{twin_id}` | Get business health score |
| `POST` | `/api/v1/strategies/{twin_id}/generate` | Generate strategies |
| `POST` | `/api/v1/insights/{twin_id}/generate` | Generate fresh insights |
| `GET` | `/api/v1/insights/{twin_id}` | Get existing insights |

### Agent & Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/agent/{twin_id}/ask` | Ask the AI agent a question |
| `POST` | `/api/v1/reports/{twin_id}/generate` | Generate PDF report |
| `GET` | `/api/v1/timeline/{twin_id}` | Get simulation timeline |
| `GET` | `/api/v1/timeline/{twin_id}/{sim_id}` | Replay a specific simulation |

## 🚨 Disaster Report Validation Layer

A modular validation pipeline for disaster/emergency reports (location,
metadata, image, duplicate detection, suspicious-report heuristics, confidence
scoring, incident clustering, reporter trust and map warning state). Every
report-creation API is automatically routed through the validation middleware.

- 📖 [Full documentation](docs/disaster-report-validation.md)
- New endpoints live under `/api/v1/disaster/*` (e.g. `POST /api/v1/disaster/reports`,
  `GET /api/v1/disaster/map/warnings`) — existing endpoints are untouched.

## 🌦️ Real-Time Route Weather Monitoring

Live weather conditions across the world shipping network, overlaid on the
Route Diversion map. Every port and sea lane shows current conditions
(temperature, wind, precipitation) and a weather-risk level
(GREEN/YELLOW/ORANGE/RED); selected voyages get an aggregated route assessment
with a recommendation. Auto-refreshes every 60s.

- Backed by the free **Open-Meteo** API (no key needed), with a deterministic
  simulated fallback so the map always renders offline.
- Endpoints: `GET /api/v1/supply-chain/routes/weather` (map overlay) and
  `GET /api/v1/supply-chain/routes/weather/route?origin=&destination=`.
- 📖 [Full documentation](docs/route-weather.md)

## 🔄 Status Workflow with Accountability Log

A generic, role-limited lifecycle engine for reports, rescues, waste,
emissions, routes and resource requests. Every transition is validated against
an explicit state machine, restricted to allowed roles, and recorded in an
append-only audit log with actor + timestamp history.

- 📖 [Full documentation](docs/status-workflow.md)
- Endpoints live under `/api/v1/workflow/*` (e.g.
  `POST /api/v1/workflow/report/{id}/transitions`,
  `GET /api/v1/workflow/timeline`) — existing endpoints are untouched.

## ✅ Data Source Checklist

A per-profile provenance checklist on the **Digital Twin** page: every source
feeding the business profile (company data, financials, operations, market,
AI artifacts, real-time news) is audited with status, coverage %, field-level
checks, and an owner/agent. Mark sections complete — the saved state persists
(`profile_checklists` table). Section-level **search + filters** (section,
status, owner, missing-data) with match highlighting, a downloadable
**PDF/HTML/CSV/Markdown/JSON report export**, and a **profile selector** so
multiple business profiles each get their own checklist.

- Endpoints: `GET`/`PUT /api/v1/digital-twins/{id}/sources`,
  `GET /api/v1/digital-twins/{id}/sources/export?format=pdf|html|csv|markdown|json`
  (downloadable profile report reusing captured fields, checklist statuses,
  recommendations, and notes), plus a **cross-profile overview**
  (`GET /api/v1/digital-twins/sources/overview`) and an on-demand re-audit
  (`POST /api/v1/digital-twins/sources/refresh`) — existing endpoints are
  untouched.
- The dashboard shows a **Profile Source Coverage** gauge; the Digital Twin
  page shows a **Profile Coverage Overview** card with click-to-select rows
  and a `regressed` badge when a profile's coverage dropped below its last
  audit snapshot.
- A **scheduled auto-verify** task (`SOURCE_AUDIT_INTERVAL_MINUTES`, default
  60) re-audits every profile and logs/regression-flags coverage drops.
- The demo seeder ships one completed sample checklist; sample exports are in
  `docs/samples/`.
- 📖 [Full documentation](docs/source-checklist.md)

## 🧪 React/Next.js Frontend Integration Guide

### 1. API Client Setup

```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API request failed");
  }
  return res.json();
}

export const api = {
  // Digital Twin
  createTwin: (data: BusinessData) =>
    apiFetch<DigitalTwin>("/digital-twins", { method: "POST", body: JSON.stringify(data) }),
  getTwin: (id: string) => apiFetch<DigitalTwin>(`/digital-twins/${id}`),
  listTwins: () => apiFetch<DigitalTwin[]>("/digital-twins"),
  updateTwin: (id: string, data: BusinessData) =>
    apiFetch<DigitalTwin>(`/digital-twins/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  // Simulation
  runSimulation: (twinId: string, decision: DecisionRequest) =>
    apiFetch<Simulation>(`/simulations/${twinId}/run`, { method: "POST", body: JSON.stringify(decision) }),
  compareScenarios: (twinId: string, scenarios: WhatIfScenario[]) =>
    apiFetch<WhatIfResponse>(`/simulations/${twinId}/compare`, { method: "POST", body: JSON.stringify({ scenarios }) }),

  // Health & Strategy
  getHealthScore: (twinId: string) => apiFetch<HealthScore>(`/health/${twinId}`),
  generateStrategies: (twinId: string) =>
    apiFetch<StrategyResponse>(`/strategies/${twinId}/generate`, { method: "POST" }),

  // Agent
  askAgent: (twinId: string, question: string) =>
    apiFetch<AgentResponse>(`/agent/${twinId}/ask`, { method: "POST", body: JSON.stringify({ question }) }),

  // Insights
  generateInsights: (twinId: string) =>
    apiFetch<Insight[]>(`/insights/${twinId}/generate`, { method: "POST" }),
  getInsights: (twinId: string) => apiFetch<Insight[]>(`/insights/${twinId}`),

  // Reports
  generateReport: (twinId: string) =>
    apiFetch<Report>(`/reports/${twinId}/generate`, { method: "POST", body: JSON.stringify({}) }),

  // Timeline
  getTimeline: (twinId: string) => apiFetch<TimelineEntry[]>(`/timeline/${twinId}`),
};
```

### 2. TypeScript Types

```typescript
// types/business-twin.ts
export interface BusinessData {
  name: string;
  industry: string;
  description?: string;
  revenue: number;
  expenses: number;
  profit?: number;
  cash_flow?: number;
  customers: number;
  employees: number;
  products?: Record<string, any>;
  sales: number;
  marketing_budget: number;
  pricing?: Record<string, number>;
  inventory_summary?: Record<string, any>;
  warehouses?: Record<string, any>;
  competitors?: Record<string, any>;
  market_share: number;
  kpis?: Record<string, any>;
}

export interface DigitalTwin extends BusinessData {
  id: string;
  business_health_score: number;
  created_at: string;
  updated_at: string;
}

export interface DecisionRequest {
  decision_type: string;
  decision_params?: Record<string, any>;
}

export interface Prediction {
  current: number;
  predicted: number;
  change_percent: number;
  direction: "up" | "down" | "neutral";
}

export interface Simulation {
  id: string;
  twin_id: string;
  decision_type: string;
  decision_params: Record<string, any>;
  predictions: { [key: string]: Prediction };
  scenarios: Scenario[];
  confidence: ConfidenceResult;
  recommendation: RecommendationResult;
  explanation: ExplanationResult;
  created_at: string;
}

export interface Scenario {
  label: "Best Case" | "Expected Case" | "Worst Case";
  revenue: number;
  profit: number;
  roi: number;
  demand: number;
  risk: number;
  probability: number;
  explanation: string;
}

export interface ConfidenceResult {
  score: number;
  level: "High" | "Medium" | "Low";
  reason: string;
  supporting_factors: string[];
}

export interface RecommendationResult {
  recommendation: string;
  expected_improvement: string;
  reasoning: string;
  business_impact: string;
  alternative_strategy: string;
}

export interface ExplanationResult {
  why: string;
  factors: string[];
  positive_factors: string[];
  negative_factors: string[];
  assumptions: string[];
  limitations: string[];
}

export interface HealthScore {
  overall_score: number;
  category_scores: Record<string, number>;
  trend: "improving" | "declining" | "stable";
  suggestions: string[];
}

export interface StrategyResponse {
  strategies: Strategy[];
  summary: string;
}

export interface Strategy {
  strategy_type: string;
  title: string;
  description: string;
  expected_impact: Record<string, any>;
  reasoning: string;
  priority: "high" | "medium" | "low";
}

export interface AgentResponse {
  answer: string;
  context_used: Record<string, any>;
  confidence: number;
}

export interface Insight {
  id: string;
  insight_type: string;
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
  data?: Record<string, any>;
  created_at: string;
}

export interface WhatIfScenario {
  name: string;
  decision_type: string;
  decision_params?: Record<string, any>;
}

export interface WhatIfResponse {
  comparisons: WhatIfComparison[];
  recommendation: string;
  winner: string;
}

export interface WhatIfComparison {
  name: string;
  decision_type: string;
  revenue: number;
  profit: number;
  roi: number;
  risk: number;
  customer_growth: number;
  health_score: number;
}

export interface TimelineEntry {
  simulation_id: string;
  decision_type: string;
  decision_params: Record<string, any>;
  predicted_revenue: number;
  predicted_profit: number;
  confidence_score: number;
  recommendation?: Record<string, any>;
  created_at: string;
}

export interface Report {
  report_id: string;
  download_url: string;
  generated_at: string;
  pages: number;
}
```

### 3. React Hook Example

```typescript
// hooks/useSimulation.ts
import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { DecisionRequest, Simulation } from "@/types/business-twin";

export function useSimulation(twinId: string | null) {
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSimulation = useCallback(
    async (decision: DecisionRequest) => {
      if (!twinId) return;
      setLoading(true);
      setError(null);
      try {
        const result = await api.runSimulation(twinId, decision);
        setSimulation(result);
        return result;
      } catch (err: any) {
        setError(err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [twinId]
  );

  return { simulation, loading, error, runSimulation };
}
```

### 4. Component Usage Example

```tsx
// components/SimulationPanel.tsx
"use client";
import { useState } from "react";
import { useSimulation } from "@/hooks/useSimulation";

const DECISION_TYPES = [
  { value: "increase_price", label: "Increase Price" },
  { value: "reduce_price", label: "Reduce Price" },
  { value: "open_branch", label: "Open Branch" },
  { value: "hire_employees", label: "Hire Employees" },
  { value: "increase_marketing", label: "Increase Marketing" },
  { value: "launch_product", label: "Launch Product" },
];

export function SimulationPanel({ twinId }: { twinId: string }) {
  const [decisionType, setDecisionType] = useState("increase_price");
  const [params, setParams] = useState("{}");
  const { simulation, loading, error, runSimulation } = useSimulation(twinId);

  const handleRun = async () => {
    try {
      await runSimulation({
        decision_type: decisionType,
        decision_params: JSON.parse(params),
      });
    } catch {}
  };

  return (
    <div className="space-y-4">
      <select
        value={decisionType}
        onChange={(e) => setDecisionType(e.target.value)}
        className="border rounded p-2"
      >
        {DECISION_TYPES.map((d) => (
          <option key={d.value} value={d.value}>{d.label}</option>
        ))}
      </select>

      <textarea
        value={params}
        onChange={(e) => setParams(e.target.value)}
        placeholder='{"percent": 10}'
        className="border rounded p-2 w-full"
        rows={3}
      />

      <button
        onClick={handleRun}
        disabled={loading}
        className="bg-blue-600 text-white px-4 py-2 rounded"
      >
        {loading ? "Running..." : "Run Simulation"}
      </button>

      {error && <p className="text-red-500">{error}</p>}

      {simulation && (
        <div className="mt-4 space-y-2">
          <h3 className="font-bold">Results</h3>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(simulation.predictions).map(([key, pred]) => (
              <div key={key} className="border rounded p-3">
                <div className="text-sm text-gray-500">{key.replace(/_/g, " ")}</div>
                <div className="text-lg font-bold">
                  ${pred.predicted.toLocaleString()}
                </div>
                <div className={pred.direction === "up" ? "text-green-600" : "text-red-600"}>
                  {pred.change_percent > 0 ? "↑" : "↓"} {Math.abs(pred.change_percent).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 border rounded p-4 bg-gray-50">
            <h4 className="font-bold">AI Recommendation</h4>
            <p>{simulation.recommendation.recommendation}</p>
            <p className="text-sm text-gray-600 mt-1">
              Confidence: {simulation.confidence.score}% ({simulation.confidence.level})
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
```

## 🔑 Available Decision Types

| Decision Type | Parameters | Description |
|---------------|------------|-------------|
| `increase_price` | `percent` | Increase product pricing |
| `reduce_price` | `percent` | Reduce product pricing |
| `open_branch` | — | Open a new branch/office |
| `close_branch` | — | Close an existing branch |
| `hire_employees` | `count`, `department` | Hire new employees |
| `layoff_employees` | `count` | Reduce workforce |
| `increase_marketing` | `percent`, `channel` | Increase marketing budget |
| `reduce_marketing` | `percent` | Reduce marketing budget |
| `launch_product` | `product_name`, `price` | Launch a new product |
| `stop_product` | `product_name` | Discontinue a product |
| `enter_new_city` | `city`, `investment` | Expand to a new market |
| `change_supplier_cost` | `percent` | Change supplier costs |
| `increase_production_capacity` | `percent` | Increase production capacity |

## 🔧 LLM Configuration

The system supports **OpenAI**, **Gemini**, or a **rule-based fallback** (no API key needed).

| Provider | Env Var | Model |
|----------|---------|-------|
| OpenAI | `OPENAI_API_KEY` | `gpt-4` |
| Gemini | `GEMINI_API_KEY` | `gemini-pro` |
| Fallback | (none) | Rule-based |

Set `LLM_PROVIDER=openai` or `LLM_PROVIDER=gemini` in `.env`.

## 📊 Sample Workflow

```bash
# 1. Create a digital twin
curl -X POST http://localhost:8000/api/v1/digital-twins \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "industry": "retail",
    "revenue": 2000000,
    "expenses": 1500000,
    "customers": 500,
    "employees": 80,
    "sales": 1800000,
    "marketing_budget": 200000,
    "market_share": 5.0
  }'

# 2. Run a simulation
curl -X POST http://localhost:8000/api/v1/simulations/{TWIN_ID}/run \
  -H "Content-Type: application/json" \
  -d '{"decision_type": "increase_marketing", "decision_params": {"percent": 20}}'

# 3. Get health score
curl http://localhost:8000/api/v1/health/{TWIN_ID}

# 4. Ask the AI agent
curl -X POST http://localhost:8000/api/v1/agent/{TWIN_ID}/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Should we increase prices?"}'

# 5. Generate strategies
curl -X POST http://localhost:8000/api/v1/strategies/{TWIN_ID}/generate

# 6. Compare scenarios
curl -X POST http://localhost:8000/api/v1/simulations/{TWIN_ID}/compare \
  -H "Content-Type: application/json" \
  -d '{
    "scenarios": [
      {"name": "Raise Prices", "decision_type": "increase_price", "decision_params": {"percent": 10}},
      {"name": "More Marketing", "decision_type": "increase_marketing", "decision_params": {"percent": 20}}
    ]
  }'
```

## 🧪 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio aiosqlite

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_schemas.py -v
pytest tests/test_simulator.py -v
pytest tests/test_health.py -v
```

## 📄 License

MIT
#   T w i n - A I  
 