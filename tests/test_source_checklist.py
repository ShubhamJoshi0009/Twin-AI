"""Tests for the business-profile source checklist feature.

Covers the audit engine (coverage, status mapping, derived counts, news feed)
and the API endpoint (200 for existing twin, 404 for missing twin).
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import business_twin_ai.supply_chain.models.database as _sc_models  # noqa: F401 — registers SC tables on Base.metadata
from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.engines.source_checklist import SourceChecklistEngine
from business_twin_ai.core.models.database import Insight, ProfileChecklist
from business_twin_ai.core.schemas.schemas import BusinessData
from business_twin_ai.database import Base


@pytest.fixture
async def db_session():
    """In-memory SQLite async session."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def full_data() -> BusinessData:
    """A fully populated business profile."""
    return BusinessData(
        name="TechNova",
        industry="technology",
        description="AI logistics platform",
        revenue=2_000_000,
        expenses=1_200_000,
        cash_flow=300_000,
        customers=500,
        employees=80,
        products={"ai-router": {"share": 0.4}},
        sales=1_800_000,
        marketing_budget=150_000,
        pricing={"standard": 99},
        inventory_summary={"units": 1200},
        warehouses={"main": "Rotterdam"},
        competitors={"rival": {"share": 0.3}},
        market_share=6.5,
    )


@pytest.fixture
def sparse_data() -> BusinessData:
    """A minimal business profile with only the company name."""
    return BusinessData(name="Ghost Corp", industry="services")


async def test_full_twin_audit(db_session: AsyncSession, full_data: BusinessData):
    """A fully populated twin should score verified on all user-provided domains."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)

    checklist = await SourceChecklistEngine(db_session).build_checklist(twin.id)
    assert checklist is not None
    assert checklist.company == "TechNova"

    by_id = {item.source_id: item for item in checklist.items}
    assert by_id["company"].status == "verified"
    assert by_id["company"].coverage_score == 100.0
    assert by_id["financials"].status == "verified"
    assert by_id["customers"].status == "verified"
    assert by_id["kpis"].status == "verified"  # computed by the engine
    assert by_id["simulations"].status == "missing"  # no simulations yet
    # News feed must never fail the audit — curated fallback guarantees content.
    assert by_id["news"].coverage_score in (0.0, 80.0, 100.0)
    assert checklist.overall_coverage > 50


async def test_sparse_twin_audit(db_session: AsyncSession, sparse_data: BusinessData):
    """A nearly empty twin should score missing on most domains."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(sparse_data)

    checklist = await SourceChecklistEngine(db_session).build_checklist(twin.id)
    assert checklist is not None
    by_id = {item.source_id: item for item in checklist.items}

    # Name present but description missing → partial, not verified.
    assert by_id["company"].status == "partial"
    assert by_id["financials"].status == "missing"
    assert by_id["products"].status == "missing"
    assert checklist.missing_count >= 6
    assert checklist.overall_coverage < 40


async def test_coverage_and_status_mapping(db_session: AsyncSession, full_data: BusinessData):
    """Coverage percentages map to verified/complete/partial/missing correctly."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)

    checklist = await SourceChecklistEngine(db_session).build_checklist(twin.id)
    assert checklist is not None
    for item in checklist.items:
        score = item.coverage_score
        if item.status == "verified":
            assert score == 100.0
        elif item.status == "complete":
            assert 70 <= score < 100
        elif item.status == "partial":
            assert 0 < score < 70
        else:
            assert score == 0.0


async def test_derived_counts_reflect_insights(db_session: AsyncSession, full_data: BusinessData):
    """Creating an insight flips the AI-insights source to verified."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    db_session.add(
        Insight(twin_id=twin.id, insight_type="growth", title="T", description="D", severity="info")
    )
    await db_session.flush()

    checklist = await SourceChecklistEngine(db_session).build_checklist(twin.id)
    assert checklist is not None
    by_id = {item.source_id: item for item in checklist.items}
    assert by_id["insights"].status == "verified"
    assert by_id["insights"].checks[0].present is True
    assert by_id["insights"].checks[0].value.startswith("1")


async def test_checklist_includes_field_level_checks(
    db_session: AsyncSession, full_data: BusinessData
):
    """Field checks carry labels and human-readable values."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)

    checklist = await SourceChecklistEngine(db_session).build_checklist(twin.id)
    assert checklist is not None
    company = next(i for i in checklist.items if i.source_id == "company")
    labels = {c.label for c in company.checks}
    assert {"Business name", "Industry", "Description"} <= labels
    revenue_check = next(c for c in company.checks if c.label == "Business name")
    assert revenue_check.present is True
    assert revenue_check.value == "TechNova"


async def test_missing_twin_returns_none(db_session: AsyncSession):
    """A non-existent twin yields None (endpoint maps to 404)."""
    checklist = await SourceChecklistEngine(db_session).build_checklist(uuid.uuid4())
    assert checklist is None


async def test_owner_field_present(db_session: AsyncSession, full_data: BusinessData):
    """Every audited section carries an owner / producing agent."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)

    checklist = await SourceChecklistEngine(db_session).build_checklist(twin.id)
    assert checklist is not None
    by_id = {item.source_id: item for item in checklist.items}
    assert by_id["company"].owner == "Onboarding wizard"
    assert by_id["news"].owner == "GDELT feed"
    assert by_id["insights"].owner == "Insights engine"
    assert all(item.owner for item in checklist.items)


async def test_saved_completions_persist(db_session: AsyncSession, full_data: BusinessData):
    """Saved completion state survives and merges into later audits."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    checklist_engine = SourceChecklistEngine(db_session)

    # Save a partial completion state: financials + products marked complete.
    saved = await checklist_engine.save_completions(
        twin.id, {"financials": True, "products": True, "customers": False}
    )
    assert saved is not None
    assert saved.saved_at is not None
    by_id = {item.source_id: item for item in saved.items}
    assert by_id["financials"].completed is True and by_id["financials"].saved is True
    assert by_id["products"].completed is True and by_id["products"].saved is True
    assert by_id["customers"].completed is False and by_id["customers"].saved is True
    # Un-saved sections keep their auto-derived completion (coverage >= 70).
    assert by_id["company"].saved is False

    # A later rebuild still sees the saved state.
    rebuilt = await checklist_engine.build_checklist(twin.id)
    assert rebuilt is not None
    rebuilt_by_id = {item.source_id: item for item in rebuilt.items}
    assert rebuilt_by_id["financials"].completed is True
    assert rebuilt.saved_at == saved.saved_at

    row = (
        await db_session.execute(
            select(ProfileChecklist).where(ProfileChecklist.twin_id == twin.id)
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.completed_count == 2


async def test_save_merges_not_replaces(db_session: AsyncSession, full_data: BusinessData):
    """A partial PUT merges into the saved state instead of wiping it."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    checklist_engine = SourceChecklistEngine(db_session)

    await checklist_engine.save_completions(twin.id, {"financials": True})
    second = await checklist_engine.save_completions(twin.id, {"products": True})
    assert second is not None
    by_id = {item.source_id: item for item in second.items}
    # Both flags survive the second (partial) save.
    assert by_id["financials"].completed is True
    assert by_id["products"].completed is True
    assert by_id["customers"].completed is True  # auto-derived, untouched


async def test_delete_twin_removes_checklist(db_session: AsyncSession, full_data: BusinessData):
    """Deleting a twin cascades to its saved checklist row."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    checklist_engine = SourceChecklistEngine(db_session)
    await checklist_engine.save_completions(twin.id, {"financials": True})

    row = (
        await db_session.execute(
            select(ProfileChecklist).where(ProfileChecklist.twin_id == twin.id)
        )
    ).scalar_one_or_none()
    assert row is not None

    deleted = await engine.delete_twin(twin.id)
    assert deleted is True

    row = (
        await db_session.execute(
            select(ProfileChecklist).where(ProfileChecklist.twin_id == twin.id)
        )
    ).scalar_one_or_none()
    assert row is None


async def test_export_markdown_report(db_session: AsyncSession, full_data: BusinessData):
    """The markdown export is a self-contained project report."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    checklist_engine = SourceChecklistEngine(db_session)
    report = await checklist_engine.build_report(twin.id)
    assert report is not None

    md = checklist_engine.export_markdown(report)
    assert "# Profile Report — TechNova" in md
    assert "## Source Checklist" in md
    assert "## Field Checks" in md
    assert "| Company Profile |" in md
    assert "✅" in md or "⬜" in md
    assert "Industry" in md  # field check label from company section


async def test_export_csv_report(db_session: AsyncSession, full_data: BusinessData):
    """The CSV export is a rows-per-section status document."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    checklist_engine = SourceChecklistEngine(db_session)
    report = await checklist_engine.build_report(twin.id)
    assert report is not None

    csv_text = checklist_engine.export_csv(report)
    assert csv_text.startswith("company,industry,section_id")
    assert "TechNova" in csv_text
    assert "financials" in csv_text
    assert ",verified," in csv_text
    assert csv_text.count("\n") == len(report["checklist"].items) + 1  # header + rows


async def test_export_html_report(db_session: AsyncSession, full_data: BusinessData):
    """The HTML export reuses captured fields, statuses, and notes."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    db_session.add(
        Insight(
            twin_id=twin.id,
            insight_type="growth",
            title="Grow Asia",
            description="Expand east",
            severity="warning",
        )
    )
    await db_session.flush()
    checklist_engine = SourceChecklistEngine(db_session)
    report = await checklist_engine.build_report(twin.id)
    assert report is not None

    html = checklist_engine.export_html(report)
    assert html.startswith("<!doctype html>")
    assert "Captured Fields" in html
    assert "Source Checklist" in html
    assert "Company Profile" in html
    assert "Grow Asia" in html  # captured insight surfaces in the report
    assert "TechNova" in html


async def test_export_pdf_report(db_session: AsyncSession, full_data: BusinessData):
    """The PDF export is a valid reportlab document."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    checklist_engine = SourceChecklistEngine(db_session)
    report = await checklist_engine.build_report(twin.id)
    assert report is not None

    pdf_bytes = checklist_engine.export_pdf(report)
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 1000


async def test_pdf_escapes_generated_content(db_session: AsyncSession, full_data: BusinessData):
    """PDF generation survives markup characters in generated content."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    db_session.add(
        Insight(
            twin_id=twin.id,
            insight_type="risk",
            title="Costs & margins <b>up</b>",
            description="A&B with <tag> markup",
            severity="warning",
        )
    )
    await db_session.flush()
    checklist_engine = SourceChecklistEngine(db_session)
    report = await checklist_engine.build_report(twin.id)
    assert report is not None

    pdf_bytes = checklist_engine.export_pdf(report)
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 1000


async def test_csv_injection_sanitized(db_session: AsyncSession):
    """Formula-dangerous cells are neutralised in the CSV export."""
    import csv as csv_module

    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(
        BusinessData(name="=HYPERLINK(\"http://evil\")", industry="finance")
    )
    checklist_engine = SourceChecklistEngine(db_session)
    report = await checklist_engine.build_report(twin.id)
    assert report is not None

    csv_text = checklist_engine.export_csv(report)
    rows = list(csv_module.reader(csv_text.splitlines()))
    assert rows[1][0].startswith("'")
    assert rows[1][1] == "finance"
    assert not any(cell.startswith("=") for row in rows[1:] for cell in row)
    assert SourceChecklistEngine._csv_safe("+44 123") == "'+44 123"
    assert SourceChecklistEngine._csv_safe("normal") == "normal"


async def test_seed_creates_completed_sample_record(db_session: AsyncSession):
    """The seeder ships one fully-completed saved checklist for the demo twin."""
    from business_twin_ai.seed import seed_database

    summary = await seed_database(db_session)
    assert summary["skipped"] is False
    twin_id = uuid.UUID(summary["twin"]["id"])

    checklist = await SourceChecklistEngine(db_session).build_checklist(twin_id)
    assert checklist is not None
    assert checklist.total_sections == 12
    assert checklist.completed_count == checklist.total_sections
    assert all(item.completed for item in checklist.items)
    assert summary["counts"]["checklist_sections"] == 12


async def test_audit_all_sets_snapshot_and_detects_regression(
    db_session: AsyncSession, full_data: BusinessData
):
    """audit_all stores a snapshot and flags coverage regressions."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(full_data)
    checklist_engine = SourceChecklistEngine(db_session)

    first = await checklist_engine.audit_all()
    assert first["audited"] == 1
    assert first["regressed"] == []
    row = (
        await db_session.execute(
            select(ProfileChecklist).where(ProfileChecklist.twin_id == twin.id)
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.last_audit_coverage is not None
    assert row.last_audited_at is not None
    baseline = row.last_audit_coverage

    # Wipe most captured fields → coverage must drop below the snapshot.
    twin.revenue = 0.0
    twin.expenses = 0.0
    twin.cash_flow = 0.0
    twin.customers = 0
    twin.employees = 0
    twin.products = {}
    twin.sales = 0.0
    twin.marketing_budget = 0.0
    twin.market_share = 0.0
    twin.inventory_summary = {}
    twin.competitors = {}
    await db_session.flush()

    second = await checklist_engine.audit_all()
    assert second["audited"] == 1
    assert any("TechNova" in r for r in second["regressed"])
    assert any("coverage" in r for r in second["regressed"])

    fresh = await checklist_engine.build_checklist(twin.id)
    assert fresh is not None
    assert fresh.overall_coverage < baseline


async def test_build_overview_rows(db_session: AsyncSession, full_data: BusinessData):
    """build_overview returns one summary row per twin."""
    engine = DigitalTwinEngine(db_session)
    await engine.create_twin(full_data)
    await engine.create_twin(
        BusinessData(name="Ghost Corp", industry="services", revenue=1, expenses=1)
    )

    overview = await SourceChecklistEngine(db_session).build_overview()
    assert len(overview) == 2
    by_name = {row["company"]: row for row in overview}
    assert by_name["TechNova"]["overall_coverage"] > by_name["Ghost Corp"]["overall_coverage"]
    assert by_name["TechNova"]["total_sections"] == 12
    assert "regressed" in by_name["TechNova"]
    assert "last_audited_at" in by_name["TechNova"]


# ── API integration ─────────────────────────────────────────────────────────

async def test_sources_endpoint_ok():
    """GET /api/v1/digital-twins/{id}/sources returns the full checklist."""
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/digital-twins",
            json={
                "name": "Checklist Co",
                "industry": "retail",
                "revenue": 1_000_000,
                "expenses": 600_000,
                "customers": 120,
                "employees": 25,
                "sales": 900_000,
                "marketing_budget": 80_000,
                "market_share": 4.0,
            },
        )
        assert created.status_code == 201
        twin_id = created.json()["id"]

        r = await client.get(f"/api/v1/digital-twins/{twin_id}/sources")
        assert r.status_code == 200
        body = r.json()
        assert body["company"] == "Checklist Co"
        assert body["twin_id"] == twin_id
        assert isinstance(body["items"], list) and len(body["items"]) == 12
        assert body["overall_coverage"] >= 0
        assert (
            body["verified_count"]
            + body["complete_count"]
            + body["partial_count"]
            + body["missing_count"]
            == 12
        )
        source_ids = {i["source_id"] for i in body["items"]}
        assert {"company", "financials", "news", "simulations", "kpis"} <= source_ids


async def test_sources_endpoint_missing_twin_404():
    """GET sources for an unknown twin returns 404."""
    from business_twin_ai.app import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/v1/digital-twins/{uuid.uuid4()}/sources")
        assert r.status_code == 404


async def test_overview_and_refresh_endpoints():
    """GET /sources/overview and POST /sources/refresh work end to end."""
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for name in ("Alpha Co", "Beta Co"):
            r = await client.post(
                "/api/v1/digital-twins",
                json={"name": name, "industry": "retail", "revenue": 100_000, "expenses": 40_000},
            )
            assert r.status_code == 201

        ov = await client.get("/api/v1/digital-twins/sources/overview")
        assert ov.status_code == 200
        body = ov.json()
        names = {i["company"] for i in body["items"]}
        assert {"Alpha Co", "Beta Co"} <= names
        item = next(i for i in body["items"] if i["company"] == "Alpha Co")
        assert item["total_sections"] == 12
        assert item["regressed"] is False

        refresh = await client.post("/api/v1/digital-twins/sources/refresh")
        assert refresh.status_code == 200
        summary = refresh.json()
        assert summary["audited"] >= 2
        assert isinstance(summary["regressed"], list)


async def test_save_completions_endpoint():
    """PUT /sources persists completion state and returns the merged checklist."""
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/digital-twins",
            json={"name": "Save Co", "industry": "retail", "revenue": 100_000, "expenses": 50_000},
        )
        twin_id = created.json()["id"]

        r = await client.put(
            f"/api/v1/digital-twins/{twin_id}/sources",
            json={"completions": {"company": True, "products": True}},
        )
        assert r.status_code == 200
        body = r.json()
        by_id = {i["source_id"]: i for i in body["items"]}
        assert by_id["company"]["completed"] is True
        assert by_id["company"]["saved"] is True
        assert body["saved_at"] is not None

        # Saved state persists on the next GET.
        r2 = await client.get(f"/api/v1/digital-twins/{twin_id}/sources")
        by_id = {i["source_id"]: i for i in r2.json()["items"]}
        assert by_id["company"]["completed"] is True
        assert by_id["products"]["completed"] is True


async def test_export_endpoints():
    """Markdown and JSON exports are downloadable and contain the profile."""
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/digital-twins",
            json={
                "name": "Export Co",
                "industry": "logistics",
                "revenue": 200_000,
                "expenses": 90_000,
            },
        )
        twin_id = created.json()["id"]

        md = await client.get(f"/api/v1/digital-twins/{twin_id}/sources/export")
        assert md.status_code == 200
        assert md.headers["content-type"].startswith("text/markdown")
        assert "Export Co" in md.text
        assert "## Source Checklist" in md.text
        assert "attachment" in md.headers["content-disposition"]

        js = await client.get(
            f"/api/v1/digital-twins/{twin_id}/sources/export?format=json"
        )
        assert js.status_code == 200
        assert js.headers["content-type"].startswith("application/json")
        assert js.json()["company"] == "Export Co"
        assert len(js.json()["items"]) == 12

        csv_resp = await client.get(
            f"/api/v1/digital-twins/{twin_id}/sources/export?format=csv"
        )
        assert csv_resp.status_code == 200
        assert csv_resp.headers["content-type"].startswith("text/csv")
        assert "company,industry,section_id" in csv_resp.text
        assert "Export Co" in csv_resp.text

        html_resp = await client.get(
            f"/api/v1/digital-twins/{twin_id}/sources/export?format=html"
        )
        assert html_resp.status_code == 200
        assert html_resp.headers["content-type"].startswith("text/html")
        assert "Captured Fields" in html_resp.text
        assert "Source Checklist" in html_resp.text

        pdf_resp = await client.get(
            f"/api/v1/digital-twins/{twin_id}/sources/export?format=pdf"
        )
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"].startswith("application/pdf")
        assert pdf_resp.content[:5] == b"%PDF-"

        bad = await client.get(
            f"/api/v1/digital-twins/{twin_id}/sources/export?format=xlsx"
        )
        assert bad.status_code == 400
