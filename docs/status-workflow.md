# Status Workflow with Accountability Log

A generic, role-limited lifecycle engine for reports, rescues, waste,
emissions, routes and resource requests. Every state change is:

1. **Validated** against an explicit state machine (legal edge from the
   current state).
2. **Role-limited** — only the roles the edge declares may perform the action.
3. **Logged** in an append-only accountability table with the actor, role,
   from/to state, action, notes and timestamp.
4. **Atomic** — the audit row and the current-state update commit together, so
   the log can never disagree with the visible state.

## Architecture

```
Client
  ↓  POST /api/v1/workflow/{type}/{id}/transitions   { action, actor_id, actor_role, notes }
  ↓
StatusWorkflowEngine.transit()
  ├─ resolve workflow definition        config.py (state machines per entity type)
  ├─ load current state                 entity_status (version counter)
  ├─ find edge (from_state, action)     illegal → 422
  ├─ check role ∈ allowed_roles         unauthorized → 403
  ├─ check notes when required          missing → 422
  ├─ optimistic lock                    UPDATE … WHERE version = expected   (stale → 409)
  └─ write audit row + advance state    status_transitions (append-only) + entity_status
```

### Module layout (`business_twin_ai/workflow/`)

| Path | Responsibility |
|------|----------------|
| `config.py` | Roles + all state machines (`WorkflowDefinition`, `TransitionRule`) |
| `models/database.py` | `EntityStatus` (current state + version) and `StatusTransition` (audit log) ORM models |
| `schemas/schemas.py` | Pydantic request/response schemas |
| `engines/engine.py` | `StatusWorkflowEngine` + `WorkflowError` |
| `api/routes/workflows.py` | Transition / status / history / audit / timeline / definitions endpoints |

The engine is free of HTTP concerns: routes translate `WorkflowError`
(status 404/403/409/422) into `HTTPException`. All workflow *rules* live in
`config.py` — adding an entity type or changing policy never requires touching
engine or route code.

## Roles

| Role | Typical powers |
|------|----------------|
| `admin` | Everything (present in every transition's allowed roles) |
| `dispatcher` | Dispatch/assign operations, close-out |
| `analyst` | Review, verify, reject, approve |
| `responder` | On-site operations: resolve, complete, fulfill |
| `reporter` | Read-only (never granted transition powers) |

`actor_id` + `actor_role` are passed explicitly in the request body. In
production, replace these with the authenticated session / JWT claims — the
engine only needs the two values.

## State machines

### Report (disaster / emergency report)

```
submitted → under_review → verified → assigned → resolved → closed
    │            │             │
    └→ duplicate  └→ rejected   └→ (assign requires notes)
```

| Action | From → To | Roles | Notes |
|--------|-----------|-------|-------|
| `start_review` | submitted → under_review | analyst, admin | |
| `mark_duplicate` | submitted → duplicate | analyst, admin | ✅ required |
| `verify` | under_review → verified | analyst, admin | |
| `reject` | under_review → rejected | analyst, admin | ✅ required |
| `assign` | verified → assigned | dispatcher, admin | ✅ required |
| `resolve` | assigned → resolved | responder, dispatcher, admin | ✅ required |
| `close` | resolved → closed | dispatcher, admin | |

### Rescue

```
requested → dispatched → on_site → completed → closed
    │           │
    └───────────┴→ cancelled        (cancel from either state)
```

### Waste management request

```
reported → scheduled → collected → disposed → closed
```

### Emissions control task

```
identified → planned → implemented → verified → closed
```

### Route / diversion

```
proposed → approved → active → reverted → closed
    │
    └→ rejected
```

### Resource request

```
requested → reviewed → approved → fulfilled → closed
    │
    └→ rejected
```

## API

All endpoints are namespaced under `/api/v1/workflow` — nothing existing is
touched.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/workflow/{entity_type}/{entity_id}/register` | Start an entity's lifecycle at its initial state (idempotent; writes the audit anchor) |
| `POST` | `/api/v1/workflow/{entity_type}/{entity_id}/transitions` | Perform a role-limited transition |
| `GET` | `/api/v1/workflow/{entity_type}/{entity_id}/status` | Current state + legal next actions |
| `GET` | `/api/v1/workflow/{entity_type}/{entity_id}/history` | Full accountability timeline for one entity (oldest first) |
| `GET` | `/api/v1/workflow/definitions` | All state machines |
| `GET` | `/api/v1/workflow/audit` | Filtered global audit log (true totals) |
| `GET` | `/api/v1/workflow/timeline` | Dashboard feed — recent events across all entities |

### Example: register → review → verify (full lifecycle)

```bash
# 1. Register the report (starts at "submitted")
curl -X POST http://localhost:8000/api/v1/workflow/report/rep-100/register \
  -H "Content-Type: application/json" \
  -d '{"actor_id": "ops", "actor_role": "admin", "notes": "initial intake"}'

# 2. Analyst starts the review
curl -X POST http://localhost:8000/api/v1/workflow/report/rep-100/transitions \
  -H "Content-Type: application/json" \
  -d '{"action": "start_review", "actor_id": "analyst-1", "actor_role": "analyst"}'

# 3. Analyst verifies (role-limited: reporter would get 403)
curl -X POST http://localhost:8000/api/v1/workflow/report/rep-100/transitions \
  -H "Content-Type: application/json" \
  -d '{"action": "verify", "actor_id": "analyst-1", "actor_role": "analyst"}'

# 4. Dispatcher assigns — notes are mandatory here
curl -X POST http://localhost:8000/api/v1/workflow/report/rep-100/transitions \
  -H "Content-Type: application/json" \
  -d '{"action": "assign", "actor_id": "dispatcher-1", "actor_role": "dispatcher", "notes": "Team Bravo assigned"}'
```

### Example transition response

```json
{
  "transition": {
    "id": "7f3d…",
    "entity_type": "report",
    "entity_id": "rep-100",
    "from_state": "under_review",
    "to_state": "verified",
    "action": "verify",
    "actor_id": "analyst-1",
    "actor_role": "analyst",
    "notes": null,
    "created_at": "2026-08-08T10:31:05Z"
  },
  "status": {
    "entity_type": "report",
    "entity_id": "rep-100",
    "current_state": "verified",
    "version": 3,
    "updated_at": "2026-08-08T10:31:05Z",
    "available_actions": [
      { "action": "assign", "to_state": "assigned", "requires_notes": true, "description": "" }
    ]
  }
}
```

### Error semantics

| HTTP | Meaning |
|------|---------|
| `404` | Unknown entity type, or entity not registered |
| `403` | Actor role not allowed for this action |
| `409` | Concurrent modification (version mismatch) — refresh and retry |
| `422` | Illegal transition from current state, or missing required notes |
| `422` (schema) | Unknown role string in the payload |

## Accountability log

Every successful transition — including the initial `register` anchor — writes
one immutable row to `status_transitions`:

```json
{
  "entity_type": "report",
  "entity_id": "rep-100",
  "from_state": "under_review",
  "to_state": "verified",
  "action": "verify",
  "actor_id": "analyst-1",
  "actor_role": "analyst",
  "notes": null,
  "created_at": "2026-08-08T10:31:05Z"
}
```

Read it per entity (`/history`), filtered globally (`/audit?actor_id=…&to_state=…`),
or as a cross-entity dashboard feed (`/timeline`). The audit `total` reflects
the true match count even when `limit` truncates the returned entries.

## Concurrency

`entity_status.version` is an optimistic lock: `transit()` applies its state
update with `UPDATE … WHERE entity_type=? AND entity_id=? AND version=?` and
returns `409` when the row no longer matches (someone else transitioned first).
Nothing is written on failure, so a rejected transition never pollutes the
audit log. Registration is similarly protected by the `(entity_type,
entity_id)` unique constraint — a racing duplicate returns the existing row
instead of failing.

## Database

Tables (created automatically by `init_db()`):

- `entity_status` — `entity_type` + `entity_id` (unique), `current_state`,
  `version`, timestamps. Indexes on type and current state.
- `status_transitions` — append-only log. Indexes on `(entity_type,
  entity_id, created_at)`, `(actor_id, created_at)`, `created_at`, `to_state`
  so history/audit/timeline queries stay indexed.

## Extension points

| Point | Where | Notes |
|-------|-------|-------|
| New entity type | `workflow/config.py` | Add a `WorkflowDefinition`; engine/routes/API pick it up automatically |
| New roles | `config.py` `ALL_ROLES` | Add the role, reference it in transition rules |
| Policy change | `config.py` | Edges, allowed roles, notes-required — all data, no code |
| Auth integration | request bodies → JWT claims | Engine only consumes `actor_id`/`actor_role` |
| New actions / states | `config.py` | Add states to the tuple + edges to `transitions` |
| Conditional transitions | `engine.py` | Extend `transit()` with guard callbacks per edge |
| External audit sink | `models/database.py` + engine | Emit a webhook/event after commit |

## Tests

- `tests/test_workflow_engine.py` — unit tests: state-machine integrity,
  registration/idempotency, full lifecycles, role limits (403), illegal
  transitions (422), notes enforcement, same action from different states,
  audit filtering, timeline ordering, optimistic-lock 409, persistence.
- `tests/test_workflow_api.py` — API integration: register, full lifecycle,
  role limits, 404/409/422 error cases, definitions, audit filters, dashboard
  timeline, idempotent registration.

```bash
pytest tests/test_workflow_engine.py tests/test_workflow_api.py -v
```
