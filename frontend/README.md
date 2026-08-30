# Business Twin AI — Frontend

Enterprise executive dashboard for the **Business Twin AI** platform (Business Decision AI + Supply Chain AI modules).

Built with **Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS · shadcn/ui-style primitives · Recharts · Framer Motion · React Flow (@xyflow/react) · React Hook Form · Axios**.

---

## ✨ Feature Overview

| Area | Pages |
|---|---|
| Overview | Dashboard, Digital Twin (React Flow), AI Assistant (Chat) |
| Decision Intelligence | Scenario Simulator, Scenario Comparison, Business Insights |
| Supply Chain | Supply Chain dashboard, Suppliers (CRUD), Inventory, Logistics, Alerts Center |
| System | Reports, Timeline, Settings |

Highlights:
- **Dark / Light mode** with smooth theme transitions (next-themes), persisted sidebar + preferences.
- **⌘K command palette**, breadcrumbs, notifications, user menu.
- **Live data** from the FastAPI backend with **automatic demo-data fallback** when the API is offline (shows a "Demo data" context).
- Loading skeletons, error states with retry, empty states, toast notifications, confirmation dialogs.
- Charts: line / area / bar / pie / gauge / sparkline — all with hover tooltips, zoom (brush) and **SVG/CSV export**.
- Chat with **markdown**, **typewriter streaming**, suggested prompts and persisted history.

---

## 🚀 Getting Started

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

Environment (`frontend/.env.local`):

```env
# Backend API base URL (Business Decision AI + Supply Chain AI)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

> The backend FastAPI server (this repo's `business_twin_ai` package) runs on port 8000
> and already allows CORS from `http://localhost:3000` / `3001`.

Production build:

```bash
npm run build
npm run start      # http://localhost:3000
```

---

## 🏗️ Architecture

```
frontend/
├── src/
│   ├── app/                    # App Router
│   │   ├── layout.tsx          # Providers + fonts + toaster
│   │   ├── globals.css         # Design tokens (HSL vars, dark/light)
│   │   ├── page.tsx            # → redirect to /dashboard
│   │   └── (dashboard)/
│   │       ├── layout.tsx      # Sidebar + topbar + ⌘K shell
│   │       └── <page>/page.tsx # One folder per route (14 pages)
│   ├── components/
│   │   ├── ui/                 # Design-system primitives (shadcn-style)
│   │   ├── layout/             # Sidebar, topbar, command palette, notifications…
│   │   ├── charts/             # Recharts wrappers + export utils
│   │   ├── kpi/                # Executive KPI cards
│   │   ├── twin/               # React Flow custom nodes
│   │   ├── chat/               # Chat bubbles (markdown + typing)
│   │   ├── simulator/          # Decision picker, scenario cards
│   │   ├── shared/             # Page header, states, search, badges
│   ├── hooks/                  # use-api (React Query + mock fallback), debounce, media queries…
│   ├── lib/
│   │   ├── api/                # Axios client + endpoint functions per module
│   │   ├── mock/               # Demo dataset used when the backend is offline
│   │   ├── types.ts            # Backend response types (both modules)
│   │   ├── constants.ts        # Nav, decision types, severity themes, chart palette
│   │   └── utils.ts            # cn, currency/date/percent formatters
│   ├── providers/              # Theme, React Query, Tooltip
│   └── stores/                 # Zustand: chat history, comparison scenarios
```

---

## 🔌 Backend Integration Guide

### Base URL & client

All requests go through `src/lib/api/client.ts` (Axios, 30s timeout). Error responses are
normalized to readable messages via an interceptor.

### Endpoints consumed

**Business Decision AI** (`src/lib/api/business.ts`)

| Function | Method & Path |
|---|---|
| `createTwin` / `listTwins` / `getTwin` / `updateTwin` / `deleteTwin` | `POST/GET/PUT/DELETE /digital-twins[/{id}]` |
| `runSimulation` | `POST /simulations/{twin_id}/run` |
| `compareScenarios` | `POST /simulations/{twin_id}/compare` |
| `getDecisionTypes` | `GET /simulations/decision-types` |
| `getHealth` | `GET /health/{twin_id}` |
| `generateStrategies` | `POST /strategies/{twin_id}/generate` |
| `askAgent` | `POST /agent/{twin_id}/ask` |
| `generateInsights` / `getInsights` | `POST|GET /insights/{twin_id}[/generate]` |
| `generateReport` | `POST /reports/{twin_id}/generate` |
| `getTimeline` / `getSimulation` | `GET /timeline/{twin_id}[/{sim_id}]` |

**Supply Chain AI** (`src/lib/api/supply-chain.ts`) — all under `/api/v1/supply-chain`

| Function | Method & Path |
|---|---|
| `listSuppliers` / `createSupplier` / `updateSupplier` / `deleteSupplier` | `…/suppliers` CRUD |
| `listWarehouses` / `getWarehouseUtilization` | `…/warehouses`, `…/warehouses/{id}/utilization` |
| `listInventory` / `createInventory` / `getInventoryAnomalies` / `optimizeInventory` | `…/inventory*` |
| `listShipments` / `createShipment` / `getDelayedShipments` / `optimizeRoutes` | `…/shipments*` |
| `detectRisks` / `listActiveRisks` / `predictRisks` | `…/risks*` |
| `generateAlerts` / `listActiveAlerts` | `…/alerts*` |
| `getSupplyChainHealth` | `GET …/health` |
| `runOptimization` | `POST …/optimization` |
| `simulateScenario` | `POST …/scenarios/simulate` |
| `generateSCReport` | `POST …/reports/generate` |
| `askSupplyChainAgent` | `POST …/agent/ask` |

### Data access pattern

Every page pulls data through **React Query** hooks in `src/hooks/use-api.ts`:

```ts
const { data, isLoading, error, refetch } = useHealth(twinId);
```

- Loading → skeleton grids / rows.
- Error → `ErrorState` with **Retry** (`refetch`).
- Caching → React Query default 30s stale time + `gcTime`.
- Live polling → `refetchInterval` on suppliers/shipments/alerts/inventory/timeline.
- **Offline resilience** → if the backend is unreachable the hook returns the demo dataset
  from `src/lib/mock/mock-data.ts` (clearly the UI is showing "Demo data").

### Adding a new page / endpoint

1. Add the type in `src/lib/types.ts` (mirror the FastAPI schema).
2. Add the endpoint function in `src/lib/api/<module>.ts`.
3. Add a `useX` hook in `src/hooks/use-api.ts` with its mock fallback.
4. Register the route in `src/app/(dashboard)/<page>/page.tsx` and add a nav entry in
   `src/lib/constants.ts` (NAV_ITEMS).

### Chat routing

The chat page routes questions to the **business agent** or the **supply-chain agent**
based on keywords (supplier/inventory/warehouse/logistics/risk…).

---

## 🧩 Key Dependencies

| Package | Purpose |
|---|---|
| `next` 15 / `react` 19 / `typescript` | Framework |
| `tailwindcss` + `@tailwindcss/typography` | Styling |
| `@radix-ui/*` + `class-variance-authority` | Accessible primitives |
| `recharts` | Charts |
| `@xyflow/react` | Digital Twin graph (React Flow v12) |
| `framer-motion` | Animations / micro-interactions |
| `@tanstack/react-query` | Data fetching, caching, retries |
| `react-hook-form` + `zod` | Supplier CRUD forms |
| `react-markdown` + `remark-gfm` | Chat markdown rendering |
| `zustand` | Chat history + comparison scenarios (persisted) |
| `next-themes` | Dark/light mode |
| `sonner` | Toasts |
| `axios` | HTTP client |

---

## 🧪 Validation

```bash
npm run typecheck   # tsc --noEmit
npm run build       # production build (all routes statically prerendered)
```
