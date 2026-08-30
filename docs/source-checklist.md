# Data Source Checklist — Profile Provenance

A lightweight, per-profile checklist that shows which sections of a business
profile (digital twin) are complete before generation or review. Every data
source feeding the profile is audited with:

- **Checklist fields** — field-level checks per section (e.g. *Revenue*,
  *Expenses*, *Product catalogue*), each with a present/absent indicator and a
  human-readable value.
- **Completion indicator** — per-section status
  (`verified` / `complete` / `partial` / `missing`), coverage %, and an overall
  profile coverage ring.
- **Saved state** — users mark sections complete; the state is persisted
  (`profile_checklists` table, one row per twin) and survives across sessions.
- **One completed sample record** — the demo seeder ships a fully-audited,
  all-sections-complete checklist for the built-in twin.

The checklist also powers **section-level search & filters** and a
**project-specific report export**.

---

## Architecture

```
Digital Twin (profile)
   │  audited by
   ▼
SourceChecklistEngine          business_twin_ai/core/engines/source_checklist.py
   ├─ field audit (twin columns → coverage % per source)
   ├─ derived counts (simulations / insights / strategies)
   ├─ live market feed (GDELT, curated fallback, timeout-guarded)
   ├─ saved-state merge (ProfileChecklist row → completed flags)
   └─ audit_all(): snapshot + regression detection (scheduled & on demand)
   ▼
GET  /api/v1/digital-twins/{id}/sources
PUT  /api/v1/digital-twins/{id}/sources      (save completions)
GET  /api/v1/digital-twins/{id}/sources/export
GET  /api/v1/digital-twins/sources/overview  (all profiles)
POST /api/v1/digital-twins/sources/refresh   (re-audit now)
```

The audit is computed on demand; only the user's completion flags are stored.
Every external call (news) is timeout-guarded and falls back to curated
headlines, so the checklist always renders — and typically completes in
well under 200 ms (the news call is the only network hop).

### The 12 audited sections

| Section | Category | Owner / agent |
|---|---|---|
| Company Profile | user-provided | Onboarding wizard |
| Financials | financial | Finance entry |
| Customers & Workforce | operational | Onboarding wizard |
| Products & Pricing | operational | Onboarding wizard |
| Sales & Marketing | financial | Finance entry |
| Inventory & Logistics | operational | Logistics desk |
| Market & Competitors | market | Market radar |
| KPIs & Health | ai-generated | Health engine |
| Simulation History | ai-generated | Simulator engine |
| AI Insights | ai-generated | Insights engine |
| AI Strategies | ai-generated | Strategy engine |
| Real-time Market Feed | real-time | GDELT feed |

Status is derived from coverage: `100% → verified`, `≥70% → complete`,
`>0% → partial`, `0% → missing`. The news feed is `verified` only when GDELT
returns live headlines; curated fallback content counts as `complete` (80%).

---

## API

All endpoints live under `/api/v1/digital-twins/` and are additive — no
existing endpoint changed.

### GET `/api/v1/digital-twins/sources/overview`

One summary row per business profile — the cross-profile view used by the
**Profile Coverage Overview** card (Digital Twin page) and the dashboard
coverage gauge.

```json
{
  "generated_at": "…",
  "items": [
    {
      "twin_id": "…",
      "company": "TechNova",
      "industry": "technology",
      "overall_coverage": 81.3,
      "completed_count": 12,
      "total_sections": 12,
      "verified_count": 6,
      "complete_count": 2,
      "partial_count": 1,
      "missing_count": 3,
      "regressed": false,
      "last_audited_at": "…"
    }
  ]
}
```

### POST `/api/v1/digital-twins/sources/refresh`

Re-audits every profile right now, storing the fresh snapshot
(`last_audit_coverage`, `last_audit_verified`, `last_audited_at`) and reporting
any coverage / verified-section regressions. Runs the same routine the
scheduled auto-verify task uses.

```json
{
  "audited": 3,
  "regressed": ["Nova Foods (coverage 73.3% → 33.8%, verified sections 8 → 2)"],
  "ran_at": "…"
}
```

### GET `/api/v1/digital-twins/{twin_id}/sources`

Returns the fresh audit merged with saved completion state.

```json
{
  "twin_id": "…",
  "company": "TechNova",
  "industry": "technology",
  "overall_coverage": 81.3,
  "verified_count": 6,
  "complete_count": 2,
  "partial_count": 1,
  "missing_count": 3,
  "completed_count": 12,
  "total_sections": 12,
  "saved_at": "2026-08-08T04:44:43.157488+00:00",
  "items": [
    {
      "source_id": "company",
      "name": "Company Profile",
      "category": "user-provided",
      "owner": "Onboarding wizard",
      "status": "verified",
      "coverage_score": 100.0,
      "checks": [
        { "field": "name", "label": "Business name", "present": true, "value": "TechNova" }
      ],
      "last_updated": "…",
      "notes": "Foundational identity data entered during onboarding.",
      "completed": true,
      "saved": true
    }
  ],
  "generated_at": "…"
}
```

### PUT `/api/v1/digital-twins/{twin_id}/sources`

Persist completion state. Body: `{ "completions": { "financials": true, "products": true } }`.
Unknown `source_id`s are ignored. Returns the merged checklist (same shape as GET).

### GET `/api/v1/digital-twins/{twin_id}/sources/export?format=pdf|html|csv|markdown|json`

Project-specific report export as a downloadable file. Every format reuses the
**existing captured fields** (twin state), the **source-checklist statuses**,
**stored recommendations** (strategies), and **checklist notes** — nothing is
regenerated or invented at export time.

- `pdf` (default) — reportlab document: captured-fields table, source
  checklist table, recommendations, insights. Served as `application/pdf`.
- `html` — self-contained, printable HTML page with inline styles.
- `csv` — rows-per-section status document (one row per audited section).
- `markdown` — human-readable report: company summary, overall coverage, the
  section checklist table, field checks, recommendations, insights.
- `json` — structured checklist payload (`application/json`).

All responses set `Content-Disposition: attachment` with a slugged filename
(e.g. `technova-solutions-profile-report.pdf`).

---

## Search & filters (UI)

On the **Digital Twin** page the checklist card provides:

- **Search** — matches section name, notes, owner, category, status, and every
  field-check label/value; matches are highlighted with `<mark>`.
- **Filters** — by section (category), by owner/agent, by status, and a
  *"missing data only"* toggle (sections with incomplete coverage or an absent
  field).
- **Reset** — one click clears the search term and every filter, and an empty
  result state offers the same reset.
- **Saved state** — a checkbox per section persists completion via
  `PUT /sources` (optimistic UI, rollback on error). A `Saved · <time>` badge
  appears once state has been stored.

## Sample exports

Ready-to-judge sample reports generated from the seeded demo profile live in
[`docs/samples/`](../docs/samples/): `profile-report.pdf`, `.html`, `.csv`,
`.markdown`, and `.json`. Regenerate them at any time by exporting the demo
twin via the UI or the API.

## Scheduled auto-verify

Every `PROFILE_AUDIT_INTERVAL_SECONDS` (default **86400** — 24 h, see `config.py`;
0 disables it) the app lifespan task calls `SourceChecklistEngine.audit_all()`
in the background:

- each profile is re-audited and its snapshot (`last_audit_coverage`,
  `last_audit_verified`, `last_audited_at`) is refreshed on the `ProfileChecklist`
  row;
- any profile whose coverage or verified-section count dropped below its last
  snapshot is logged as a **regression** and surfaced via
  `GET /sources/overview` (`regressed: true`) and the refresh endpoint;
- the task is a plain `asyncio` background task (no new dependencies) and is
  skipped gracefully if the settings are disabled or the loop is shutting down.

You can also re-audit manually any time with `POST /sources/refresh` or via
`SourceChecklistEngine(db).audit_all()`.

## Seeding

`seed_database()` audits the demo twin and saves a fully-completed checklist,
so a fresh install demonstrates the finished record immediately. `--force`
reseeds it along with the rest of the demo data.

## Extension points

- **Add a section** — append an entry to `_SOURCE_CATALOGUE` (and an owner in
  `_OWNER_BY_SOURCE`) in `source_checklist.py`; the audit, UI, filters, and
  export pick it up automatically.
- **New check fields** — add `(attr, label)` pairs to a section's `fields`;
  values are summarized by `_summarize`.
- **Additional live sources** — mirror `_audit_live`: fetch with a timeout,
  always fall back, and return a `SourceChecklistItem`.
- **New export formats** — add a branch in the `/sources/export` route and a
  renderer on the engine (e.g. `export_docx`); `build_report` already
  assembles everything a renderer needs (state, checklist, strategies,
  insights).
