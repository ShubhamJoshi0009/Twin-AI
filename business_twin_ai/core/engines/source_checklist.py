"""Data-source checklist for business profiles (digital twins).

Every business profile is built from several data sources: user-provided
company data, derived AI artifacts (simulations, insights, strategies), and
real-time market context. This engine audits each source and produces a
checklist showing what is present, how complete it is, how fresh it is, and
what is still missing — so users can see at a glance the provenance and
coverage of the numbers behind their digital twin.

Each audit is computed on demand (no extra persistence), stays backward
compatible, and every external call (news) is timeout-guarded and falls back
to a curated feed so the checklist always renders.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.models.database import (
    DigitalTwin,
    Insight,
    ProfileChecklist,
    Simulation,
    Strategy,
)
from business_twin_ai.core.schemas.schemas import (
    SourceCheck,
    SourceChecklistItem,
    SourceChecklistResponse,
)
from business_twin_ai.services.news.gdelt import fetch_market_news

logger = logging.getLogger(__name__)

# Optional reverse-geocode / live checks are skipped here — the checklist only
# touches data the platform already produces, so it runs in well under 200 ms.
_NEWS_TIMEOUT_SECONDS = 4.0

# ── Static source catalogue ──────────────────────────────────────────────────
# Each entry maps one audit domain to the twin fields it covers. Field values
# are summarized with ``_summarize`` (numbers, dicts, lists each formatted).
_OWNER_BY_SOURCE = {
    "company": "Onboarding wizard",
    "financials": "Finance entry",
    "customers": "Onboarding wizard",
    "products": "Onboarding wizard",
    "sales": "Finance entry",
    "inventory": "Logistics desk",
    "market": "Market radar",
    "kpis": "Health engine",
    "simulations": "Simulator engine",
    "insights": "Insights engine",
    "strategies": "Strategy engine",
    "news": "GDELT feed",
}

_SOURCE_CATALOGUE: List[Dict[str, Any]] = [
    {
        "source_id": "company",
        "name": "Company Profile",
        "category": "user-provided",
        "fields": [
            ("name", "Business name"),
            ("industry", "Industry"),
            ("description", "Description"),
        ],
        "notes": "Foundational identity data entered during onboarding.",
    },
    {
        "source_id": "financials",
        "name": "Financials",
        "category": "financial",
        "fields": [
            ("revenue", "Revenue"),
            ("expenses", "Expenses"),
            ("profit", "Profit"),
            ("cash_flow", "Cash flow"),
        ],
        "notes": "Balance-sheet style inputs driving profit margin and cash-flow KPIs.",
    },
    {
        "source_id": "customers",
        "name": "Customers & Workforce",
        "category": "operational",
        "fields": [("customers", "Customers"), ("employees", "Employees")],
        "notes": "Demand base and headcount feeding per-customer economics.",
    },
    {
        "source_id": "products",
        "name": "Products & Pricing",
        "category": "operational",
        "fields": [("products", "Product catalogue"), ("pricing", "Pricing model")],
        "notes": "SKU mix and price structure used by sales simulations.",
    },
    {
        "source_id": "sales",
        "name": "Sales & Marketing",
        "category": "financial",
        "fields": [("sales", "Sales"), ("marketing_budget", "Marketing budget")],
        "notes": "Revenue engine inputs including marketing ROI.",
    },
    {
        "source_id": "inventory",
        "name": "Inventory & Logistics",
        "category": "operational",
        "fields": [
            ("inventory_summary", "Inventory summary"),
            ("warehouses", "Warehouse footprint"),
        ],
        "notes": "Stock and distribution footprint for logistics simulations.",
    },
    {
        "source_id": "market",
        "name": "Market & Competitors",
        "category": "market",
        "fields": [("competitors", "Competitors"), ("market_share", "Market share")],
        "notes": "Competitive positioning and share assumptions.",
    },
    {
        "source_id": "kpis",
        "name": "KPIs & Health",
        "category": "ai-generated",
        "fields": [("kpis", "KPI set"), ("business_health_score", "Health score")],
        "notes": "Derived metrics computed automatically from the raw profile.",
    },
    {
        "source_id": "simulations",
        "name": "Simulation History",
        "category": "ai-generated",
        "derived": True,
        "notes": "Decision simulations run against the twin.",
    },
    {
        "source_id": "insights",
        "name": "AI Insights",
        "category": "ai-generated",
        "derived": True,
        "notes": "Rule / LLM generated insights from profile analysis.",
    },
    {
        "source_id": "strategies",
        "name": "AI Strategies",
        "category": "ai-generated",
        "derived": True,
        "notes": "Generated strategic recommendations with expected impact.",
    },
    {
        "source_id": "news",
        "name": "Real-time Market Feed",
        "category": "real-time",
        "live": True,
        "notes": "Live GDELT headlines (curated fallback when offline).",
    },
]


def _summarize(value: Any, max_len: int = 60) -> str:
    """Human-readable one-line summary of a twin field value."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
    if isinstance(value, dict):
        if not value:
            return ""
        return ", ".join(f"{k}: {_summarize(v)}" for k, v in list(value.items())[:4])[:max_len]
    if isinstance(value, (list, tuple, set)):
        return f"{len(value)} item(s)" if value else ""
    text = str(value).strip().replace("\n", " ")
    return text[:max_len]


def _status_for(coverage: float) -> str:
    """Map a coverage percentage to a checklist status."""
    if coverage >= 100:
        return "verified"
    if coverage >= 70:
        return "complete"
    if coverage > 0:
        return "partial"
    return "missing"


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise a (possibly naive, SQLite-stored) datetime to UTC-aware."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SourceChecklistEngine:
    """Audits a digital twin's data sources and produces a checklist."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_checklist(self, twin_id: uuid.UUID) -> Optional[SourceChecklistResponse]:
        """Build the full source checklist for a digital twin.

        Returns ``None`` when the twin does not exist. Runs the twin-field
        audit locally and derives counts from the database; the only external
        call (news feed) is timeout-guarded and never fails the request.
        """
        twin = await self._get_twin(twin_id)
        if twin is None:
            return None

        items: List[SourceChecklistItem] = []

        for spec in _SOURCE_CATALOGUE:
            if spec.get("live"):
                item = await self._audit_live(twin)
            elif spec.get("derived"):
                item = await self._audit_derived(twin_id, spec)
            else:
                item = self._audit_fields(twin, spec)
            items.append(item)

        coverage = round(sum(i.coverage_score for i in items) / len(items), 1) if items else 0.0
        counts = {"verified": 0, "complete": 0, "partial": 0, "missing": 0}
        for item in items:
            counts[item.status] += 1

        # Merge saved completion state (survives across sessions).
        saved_at: Optional[str] = None
        saved_completions: Dict[str, bool] = {}
        saved = await self._get_saved(twin_id)
        if saved is not None:
            saved_at_dt = _as_utc(saved.saved_at)
            saved_at = saved_at_dt.isoformat() if saved_at_dt else None
            for section in saved.sections or []:
                sid = section.get("source_id") if isinstance(section, dict) else None
                if sid:
                    saved_completions[sid] = bool(section.get("completed", False))

        completed_count = 0
        for item in items:
            if item.source_id in saved_completions:
                item.completed = saved_completions[item.source_id]
                item.saved = True
            else:
                item.completed = item.coverage_score >= 70
            completed_count += 1 if item.completed else 0

        return SourceChecklistResponse(
            twin_id=twin.id,
            company=twin.name,
            industry=twin.industry,
            overall_coverage=coverage,
            verified_count=counts["verified"],
            complete_count=counts["complete"],
            partial_count=counts["partial"],
            missing_count=counts["missing"],
            completed_count=completed_count,
            total_sections=len(items),
            saved_at=saved_at,
            items=items,
            generated_at=datetime.now(timezone.utc),
        )

    async def save_completions(
        self, twin_id: uuid.UUID, completions: Dict[str, bool]
    ) -> Optional[SourceChecklistResponse]:
        """Persist completion flags for a twin's source checklist.

        Stores the user's saved state, then returns the freshly rebuilt
        checklist (audit + saved state merged). Returns ``None`` when the twin
        does not exist.
        """
        twin = await self._get_twin(twin_id)
        if twin is None:
            return None

        saved = await self._get_saved(twin_id)
        if saved is None:
            saved = ProfileChecklist(twin_id=twin_id)
            self.db.add(saved)

        # Merge: keep previously saved sections, update only the supplied keys
        # (a partial PUT must never wipe other saved flags).
        valid_ids = {spec["source_id"] for spec in _SOURCE_CATALOGUE}
        current = {
            s.get("source_id"): bool(s.get("completed", False))
            for s in (saved.sections or [])
            if isinstance(s, dict) and s.get("source_id")
        }
        current.update(
            {sid: bool(completed) for sid, completed in completions.items() if sid in valid_ids}
        )
        sections = [
            {"source_id": sid, "completed": comp} for sid, comp in sorted(current.items())
        ]
        saved.sections = sections
        saved.completed_count = sum(1 for s in sections if s["completed"])
        saved.overall_completion = round(
            saved.completed_count / len(valid_ids) * 100, 1
        ) if valid_ids else 0.0
        saved.saved_at = datetime.now(timezone.utc)

        await self.db.flush()
        return await self.build_checklist(twin_id)

    async def build_overview(self) -> List[Dict[str, Any]]:
        """Per-profile coverage summary across every digital twin."""
        twins = (
            await self.db.execute(select(DigitalTwin).order_by(DigitalTwin.created_at))
        ).scalars().all()
        saved_by_twin = await self._saved_rows()
        items: List[Dict[str, Any]] = []
        for twin in twins:
            saved = saved_by_twin.get(twin.id)
            checklist = await self.build_checklist(twin.id)
            if checklist is None:
                continue
            prev_coverage = saved.last_audit_coverage if saved else None
            regressed = prev_coverage is not None and (
                checklist.overall_coverage < prev_coverage - 0.5
            )
            last_audited = _as_utc(saved.last_audited_at) if saved else None
            items.append(
                {
                    "twin_id": twin.id,
                    "company": twin.name,
                    "industry": twin.industry,
                    "overall_coverage": checklist.overall_coverage,
                    "completed_count": checklist.completed_count,
                    "total_sections": checklist.total_sections,
                    "verified_count": checklist.verified_count,
                    "complete_count": checklist.complete_count,
                    "partial_count": checklist.partial_count,
                    "missing_count": checklist.missing_count,
                    "regressed": regressed,
                    "last_audited_at": last_audited.isoformat() if last_audited else None,
                }
            )
        return items

    async def audit_all(self) -> Dict[str, Any]:
        """Re-audit every profile and flag coverage regressions.

        Compares each fresh audit against the snapshot stored on the twin's
        ProfileChecklist row; logs and collects any profile whose overall
        coverage or verified-section count dropped, then refreshes the
        snapshot. Used by the scheduled auto-verify task and the refresh API.
        """
        twins = (
            await self.db.execute(select(DigitalTwin).order_by(DigitalTwin.created_at))
        ).scalars().all()
        saved_by_twin = await self._saved_rows()
        flagged: Dict[str, List[str]] = {}
        for twin in twins:
            saved = saved_by_twin.get(twin.id)
            prev_coverage = saved.last_audit_coverage if saved else None
            prev_verified = saved.last_audit_verified if saved else None
            checklist = await self.build_checklist(twin.id)
            if checklist is None:
                continue
            if prev_coverage is not None and checklist.overall_coverage < prev_coverage - 0.5:
                flagged.setdefault(twin.name, []).append(
                    f"coverage {prev_coverage:g}% → {checklist.overall_coverage:g}%"
                )
            if prev_verified is not None and checklist.verified_count < prev_verified:
                flagged.setdefault(twin.name, []).append(
                    f"verified sections {prev_verified} → {checklist.verified_count}"
                )
            if saved is None:
                saved = ProfileChecklist(twin_id=twin.id)
                self.db.add(saved)
            saved.last_audit_coverage = checklist.overall_coverage
            saved.last_audit_verified = checklist.verified_count
            saved.last_audited_at = datetime.now(timezone.utc)
        await self.db.flush()

        regressed = [f"{name} ({', '.join(reasons)})" for name, reasons in flagged.items()]
        if regressed:
            logger.warning("Profile source regression detected: %s", "; ".join(regressed))
        return {
            "audited": len(twins),
            "regressed": regressed,
            "ran_at": datetime.now(timezone.utc),
        }

    async def build_report(self, twin_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Assemble everything a profile report needs in one payload.

        Reuses the existing captured fields (twin state), the source-checklist
        statuses, stored strategies (recommendations), and checklist notes.
        Returns ``None`` when the twin does not exist.
        """
        twin = await self._get_twin(twin_id)
        if twin is None:
            return None
        checklist = await self.build_checklist(twin_id)
        strategies = await self._recent_artifacts(twin_id, Strategy)
        insights = await self._recent_artifacts(twin_id, Insight)
        return {
            "twin_id": twin_id,
            "company": twin.name,
            "industry": twin.industry,
            "description": twin.description or "",
            "health_score": twin.business_health_score,
            "state": DigitalTwinEngine(self.db).get_twin_state(twin),
            "checklist": checklist,
            "strategies": strategies,
            "insights": insights,
            "generated_at": datetime.now(timezone.utc),
        }

    def export_markdown(self, report: Dict[str, Any]) -> str:
        """Render the profile report as Markdown.

        Company summary, overall coverage, the section checklist with status /
        owner / coverage / completion, field checks, recommendations, and
        captured insights.
        """
        checklist: SourceChecklistResponse = report["checklist"]
        lines: List[str] = []
        lines.append(f"# Profile Report — {checklist.company}")
        lines.append("")
        lines.append(f"**Industry:** {checklist.industry}  ")
        lines.append(f"**Health score:** {report['health_score']:g}/100  ")
        lines.append(
            f"**Overall coverage:** {checklist.overall_coverage:g}%  "
            f"| **Completed:** {checklist.completed_count}/{checklist.total_sections}  "
            f"| **Generated:** {report['generated_at'].isoformat()}"
        )
        if checklist.saved_at:
            lines.append(f"**Saved state:** {checklist.saved_at}")
        if report.get("description"):
            lines.append(f"**Description:** {report['description']}")
        lines.append("")
        lines.append("## Captured Fields")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        state: Dict[str, Any] = report["state"]
        for key, label in [
            ("revenue", "Revenue"),
            ("expenses", "Expenses"),
            ("profit", "Profit"),
            ("cash_flow", "Cash flow"),
            ("customers", "Customers"),
            ("employees", "Employees"),
            ("sales", "Sales"),
            ("marketing_budget", "Marketing budget"),
            ("market_share", "Market share (%)"),
        ]:
            lines.append(f"| {label} | {state.get(key, 0)} |")
        lines.append("")
        lines.append("## Source Checklist")
        lines.append("")
        lines.append(
            "| Section | Category | Owner | Status | Coverage | Completed | Last updated |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for item in checklist.items:
            lines.append(
                f"| {item.name} | {item.category} | {item.owner or '—'} | "
                f"{item.status} | {item.coverage_score:g}% | "
                f"{'✅' if item.completed else '⬜'} | {item.last_updated or '—'} |"
            )
        lines.append("")
        lines.append("## Field Checks")
        for item in checklist.items:
            lines.append("")
            lines.append(f"### {item.name} — {item.status} ({item.coverage_score:g}%)")
            lines.append(f"_{item.notes}_")
            if item.checks:
                for check in item.checks:
                    mark = "✅" if check.present else "❌"
                    value = check.value if check.present else "not provided"
                    lines.append(f"- {mark} **{check.label}**: {value}")
            else:
                lines.append("- no field checks")
        if report["strategies"]:
            lines.append("")
            lines.append("## Recommendations")
            for s in report["strategies"]:
                lines.append("")
                lines.append(f"- **{s.title}** *(priority: {s.priority})* — {s.description}")
        if report["insights"]:
            lines.append("")
            lines.append("## Insights")
            for i in report["insights"]:
                lines.append(f"- [{i.severity}] {i.title} — {i.description}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _csv_safe(value: Any) -> str:
        """Neutralise CSV formula injection (cells starting with = + - @)."""
        text = str(value or "")
        if text and text[0] in "=+-@":
            return "'" + text
        return text

    def export_csv(self, report: Dict[str, Any]) -> str:
        """Render the source-checklist statuses as a CSV document."""
        checklist: SourceChecklistResponse = report["checklist"]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "company", "industry", "section_id", "section", "category", "owner",
                "status", "coverage_score", "completed", "last_updated", "notes",
            ]
        )
        for item in checklist.items:
            writer.writerow(
                [
                    self._csv_safe(checklist.company),
                    self._csv_safe(checklist.industry),
                    item.source_id,
                    self._csv_safe(item.name),
                    item.category,
                    self._csv_safe(item.owner),
                    item.status,
                    f"{item.coverage_score:g}",
                    "yes" if item.completed else "no",
                    self._csv_safe(item.last_updated),
                    self._csv_safe(item.notes),
                ]
            )
        return buf.getvalue()

    def export_html(self, report: Dict[str, Any]) -> str:
        """Render a self-contained, printable HTML report."""
        checklist: SourceChecklistResponse = report["checklist"]
        state: Dict[str, Any] = report["state"]
        status_color = {
            "verified": "#16a34a",
            "complete": "#2563eb",
            "partial": "#d97706",
            "missing": "#dc2626",
        }

        def esc(value: Any) -> str:
            text = _summarize(value) if not isinstance(value, str) else value
            return (
                str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        rows: List[str] = []
        for item in checklist.items:
            color = status_color.get(item.status, "#6b7280")
            rows.append(
                "<tr>"
                f"<td><strong>{esc(item.name)}</strong><br/><small>{esc(item.notes)}</small></td>"
                f"<td>{esc(item.category)}</td>"
                f"<td>{esc(item.owner)}</td>"
                f"<td><span style='color:{color};font-weight:600'>{item.status}</span></td>"
                f"<td style='text-align:right'>{item.coverage_score:g}%</td>"
                f"<td style='text-align:center'>{'✓' if item.completed else '—'}</td>"
                "</tr>"
            )

        field_pairs: List[str] = []
        for key, label in [
            ("revenue", "Revenue"),
            ("expenses", "Expenses"),
            ("profit", "Profit"),
            ("cash_flow", "Cash flow"),
            ("customers", "Customers"),
            ("employees", "Employees"),
            ("sales", "Sales"),
            ("marketing_budget", "Marketing budget"),
            ("market_share", "Market share (%)"),
        ]:
            value = state.get(key, 0)
            field_pairs.append(f"<td><small>{label}</small><br/><strong>{esc(value)}</strong></td>")

        strat_rows = "".join(
            (
                "<li><strong>"
                f"{esc(s.title)}</strong> <em>({esc(s.priority)})</em> — {esc(s.description)}</li>"
            )
            for s in report["strategies"]
        )
        insight_rows = "".join(
            f"<li><strong>[{esc(i.severity)}]</strong> {esc(i.title)} — {esc(i.description)}</li>"
            for i in report["insights"]
        )

        return (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'/>"
            "<title>Profile Report — "
            f"{esc(checklist.company)}</title>"
            "<style>"
            "body{font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
            "color:#1f2937;max-width:860px;margin:0 auto;padding:32px;line-height:1.5}"
            "h1{border-bottom:3px solid #2563eb;padding-bottom:8px}"
            "h2{margin-top:28px;color:#111827}"
            "table{border-collapse:collapse;width:100%;font-size:13px}"
            "th,td{border:1px solid #e5e7eb;padding:8px;text-align:left;vertical-align:top}"
            "th{background:#f3f4f6}"
            ".meta{color:#6b7280;font-size:13px}"
            ".badge{display:inline-block;background:#eff6ff;color:#2563eb;"
            "border:1px solid #bfdbfe;border-radius:999px;padding:2px 10px;font-size:12px}"
            "@media print{body{padding:12px}}"
            "</style></head><body>"
            f"<h1>Profile Report — {esc(checklist.company)}</h1>"
            f"<p class='meta'>Industry: {esc(checklist.industry)} · "
            f"Health score: {report['health_score']:g}/100 · "
            f"Coverage: {checklist.overall_coverage:g}% · "
            f"Generated: {report['generated_at'].isoformat()}</p>"
            "<h2>Captured Fields</h2><table><tr>"
            + "".join(field_pairs)
            + "</tr></table>"
            "<h2>Source Checklist</h2><table>"
            "<tr><th>Section</th><th>Category</th><th>Owner</th>"
            "<th>Status</th><th>Coverage</th><th>Completed</th></tr>"
            + "".join(rows)
            + "</table>"
            + (f"<h2>Recommendations</h2><ul>{strat_rows}</ul>" if strat_rows else "")
            + (f"<h2>Insights</h2><ul>{insight_rows}</ul>" if insight_rows else "")
            + "<p class='meta'>Exported by Business Twin AI · "
            f"{checklist.completed_count}/{checklist.total_sections} sections complete</p>"
            "</body></html>"
        )

    def export_pdf(self, report: Dict[str, Any]) -> bytes:
        """Render the profile report as a PDF (reportlab), returned as bytes."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        checklist: SourceChecklistResponse = report["checklist"]
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch
        )
        styles = getSampleStyleSheet()
        story: List[Any] = []

        story.append(Paragraph(f"Profile Report: {checklist.company}", styles["Title"]))
        header_parts = [
            f"Industry: {checklist.industry}",
            f"Health: {report['health_score']:g}/100",
            f"Coverage: {checklist.overall_coverage:g}%",
            f"Generated: {report['generated_at'].isoformat()}",
        ]
        story.append(Paragraph(" · ".join(header_parts), styles["Normal"]))
        if report.get("description"):
            story.append(Paragraph(xml_escape(report["description"]), styles["Normal"]))
        story.append(Spacer(1, 0.25 * inch))

        story.append(Paragraph("Captured Fields", styles["Heading1"]))
        state: Dict[str, Any] = report["state"]
        field_rows = [["Field", "Value"]]
        for key, label in [
            ("revenue", "Revenue"),
            ("expenses", "Expenses"),
            ("profit", "Profit"),
            ("cash_flow", "Cash flow"),
            ("customers", "Customers"),
            ("employees", "Employees"),
            ("sales", "Sales"),
            ("marketing_budget", "Marketing budget"),
            ("market_share", "Market share (%)"),
        ]:
            field_rows.append([label, str(state.get(key, 0))])
        field_table = Table(field_rows, colWidths=[2.5 * inch, 3.5 * inch])
        field_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f3f4f6")],
                    ),
                ]
            )
        )
        story.append(field_table)
        story.append(Spacer(1, 0.25 * inch))

        story.append(Paragraph("Source Checklist", styles["Heading1"]))
        checklist_rows = [["Section", "Owner", "Status", "Coverage", "Complete"]]
        for item in checklist.items:
            checklist_rows.append(
                [
                    item.name,
                    item.owner,
                    item.status,
                    f"{item.coverage_score:g}%",
                    "Yes" if item.completed else "No",
                ]
            )
        cl_table = Table(
            checklist_rows,
            colWidths=[2.2 * inch, 1.6 * inch, 1.0 * inch, 1.0 * inch, 0.8 * inch],
        )
        cl_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#059669")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f0fdf4")],
                    ),
                ]
            )
        )
        story.append(cl_table)
        story.append(Spacer(1, 0.25 * inch))

        if report["strategies"]:
            story.append(Paragraph("Recommendations", styles["Heading1"]))
            for s in report["strategies"]:
                story.append(
                    Paragraph(
                        f"<b>{xml_escape(s.title)}</b> "
                        f"(priority: {xml_escape(s.priority)}) — {xml_escape(s.description)}",
                        styles["Normal"],
                    )
                )
                story.append(Spacer(1, 0.08 * inch))

        if report["insights"]:
            story.append(Paragraph("Insights", styles["Heading1"]))
            for ins in report["insights"]:
                severity_color = {
                    "critical": "#dc2626",
                    "warning": "#d97706",
                    "info": "#2563eb",
                }.get(ins.severity, "#2563eb")
                story.append(
                    Paragraph(
                        f'<font color="{severity_color}">'
                        f"[{xml_escape(ins.severity.upper())}]</font> "
                        f"<b>{xml_escape(ins.title)}</b> — {xml_escape(ins.description)}",
                        styles["Normal"],
                    )
                )
                story.append(Spacer(1, 0.08 * inch))

        doc.build(story)
        return buf.getvalue()

    # ── Internals ────────────────────────────────────────────────────────────

    async def _get_twin(self, twin_id: uuid.UUID) -> Optional[DigitalTwin]:
        result = await self.db.execute(select(DigitalTwin).where(DigitalTwin.id == twin_id))
        return result.scalar_one_or_none()

    async def _get_saved(self, twin_id: uuid.UUID) -> Optional[ProfileChecklist]:
        result = await self.db.execute(
            select(ProfileChecklist).where(ProfileChecklist.twin_id == twin_id)
        )
        return result.scalar_one_or_none()

    async def _saved_rows(self) -> Dict[uuid.UUID, ProfileChecklist]:
        """Load every saved checklist row in one query, keyed by twin_id.

        Avoids the per-twin N+1 lookups in ``build_overview`` / ``audit_all``
        when many business profiles exist.
        """
        rows = (await self.db.execute(select(ProfileChecklist))).scalars().all()
        return {row.twin_id: row for row in rows}

    def _audit_fields(self, twin: DigitalTwin, spec: Dict[str, Any]) -> SourceChecklistItem:
        """Audit a twin for the field-based sources in the catalogue."""
        checks: List[SourceCheck] = []
        present = 0
        for attr, label in spec["fields"]:
            value = getattr(twin, attr, None)
            filled = bool(value)
            present += 1 if filled else 0
            checks.append(
                SourceCheck(
                    field=attr,
                    label=label,
                    present=filled,
                    value=_summarize(value) if filled else "",
                )
            )
        coverage = round(present / len(checks) * 100, 1)
        return SourceChecklistItem(
            source_id=spec["source_id"],
            name=spec["name"],
            category=spec["category"],
            owner=_OWNER_BY_SOURCE.get(spec["source_id"], ""),
            status=_status_for(coverage),
            coverage_score=coverage,
            checks=checks,
            last_updated=twin.updated_at.isoformat() if twin.updated_at else None,
            notes=spec["notes"],
        )

    async def _audit_derived(self, twin_id: uuid.UUID, spec: Dict[str, Any]) -> SourceChecklistItem:
        """Audit derived AI artifacts by counting database records for the twin."""
        model = {
            "simulations": Simulation,
            "insights": Insight,
            "strategies": Strategy,
        }[spec["source_id"]]
        count = await self._count_for_twin(model, twin_id)
        checks = [
            SourceCheck(
                field="history",
                label=f"{spec['name']} records",
                present=count > 0,
                value=f"{count} record(s)" if count else "",
            )
        ]
        # Surface recent generated titles so the search box covers actual
        # generated content (insights / strategies), not just record counts.
        if spec["source_id"] in ("insights", "strategies"):
            titles = await self._recent_titles(model, twin_id)
            checks.append(
                SourceCheck(
                    field="recent",
                    label=f"Recent {spec['name'].lower()}",
                    present=bool(titles),
                    value=" | ".join(titles) if titles else "",
                )
            )
        coverage = 100.0 if count > 0 else 0.0
        return SourceChecklistItem(
            source_id=spec["source_id"],
            name=spec["name"],
            category=spec["category"],
            owner=_OWNER_BY_SOURCE.get(spec["source_id"], ""),
            status=_status_for(coverage),
            coverage_score=coverage,
            checks=checks,
            notes=spec["notes"],
        )

    async def _count_for_twin(self, model: Any, twin_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(model).where(model.twin_id == twin_id)
        )
        return int(result.scalar() or 0)

    async def _recent_titles(self, model: Any, twin_id: uuid.UUID, limit: int = 3) -> List[str]:
        """Fetch the most recent titles of a generated-content model for a twin."""
        result = await self.db.execute(
            select(model.title)
            .where(model.twin_id == twin_id)
            .order_by(model.created_at.desc())
            .limit(limit)
        )
        return [str(title) for title in result.scalars().all()]

    async def _recent_artifacts(self, twin_id: uuid.UUID, model: Any, limit: int = 4) -> List[Any]:
        """Fetch the most recent full records (strategies / insights) for a twin."""
        result = await self.db.execute(
            select(model)
            .where(model.twin_id == twin_id)
            .order_by(model.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _audit_live(self, twin: DigitalTwin) -> SourceChecklistItem:
        """Audit the real-time market feed (GDELT with curated fallback)."""
        query = f"{twin.industry} {twin.name} supply chain market"
        last_updated: Optional[str] = None
        notes = "Real-time market headlines grounding the analysis."
        try:
            articles = await asyncio.wait_for(
                fetch_market_news(query, limit=5), timeout=_NEWS_TIMEOUT_SECONDS
            )
        except Exception as exc:  # noqa: BLE001 — never fail the checklist on network trouble
            logger.info("Market feed unavailable for checklist (%s)", exc)
            articles = []

        live = bool(articles) and any(
            not (a.get("url") or "").startswith("https://news.google.com") for a in articles
        )
        newest: Optional[datetime] = None
        for a in articles:
            published = a.get("published_at")
            if not published:
                continue
            try:
                parsed = datetime.fromisoformat(published)
            except ValueError:
                continue
            if newest is None or parsed > newest:
                newest = parsed

        if newest is not None:
            last_updated = newest.isoformat()
            age_hours = max(0, int((datetime.now(timezone.utc) - newest).total_seconds() / 3600))
            mode = "Live GDELT feed" if live else "Curated fallback feed"
            notes = f"{mode} · headlines {age_hours}h old"
        elif not articles:
            notes = "No headlines available — check connectivity and retry."

        checks = [
            SourceCheck(
                field="headlines",
                label="Market headlines",
                present=bool(articles),
                value=f"{len(articles)} headline(s)" if articles else "",
            ),
            SourceCheck(
                field="provider",
                label="Provider",
                present=live,
                value="GDELT (live)" if live else "curated fallback",
            ),
        ]
        # Curated fallback content is present but not live-verified → complete/80.
        coverage = 100.0 if live else (80.0 if articles else 0.0)
        return SourceChecklistItem(
            source_id="news",
            name="Real-time Market Feed",
            category="real-time",
            owner=_OWNER_BY_SOURCE["news"],
            status="verified" if live else ("complete" if articles else "missing"),
            coverage_score=coverage,
            checks=checks,
            last_updated=last_updated,
            notes=notes,
        )
