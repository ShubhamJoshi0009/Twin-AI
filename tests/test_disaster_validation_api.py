"""API integration tests for the disaster report validation endpoints.

Runs against the real FastAPI app (middleware included) over ASGI. The shared
SQLite test DB is used, so each test cleans up the disaster tables it creates.
"""

from __future__ import annotations

import asyncio
import base64
import struct
import uuid
import zlib
from datetime import datetime, timedelta, timezone

import httpx
import pytest

# ── Test configuration ───────────────────────────────────────────────────────
# conftest.py already froze DATABASE_URL to a shared SQLite file; importing the
# app here registers the disaster routes + validation middleware.

from business_twin_ai.app import app  # noqa: E402
from business_twin_ai.database import init_db  # noqa: E402
from business_twin_ai.disaster.models import DisasterReport, IncidentCluster, ReporterProfile  # noqa: E402


def make_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 400, 300, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" + b"\x00\x00\x00" * 400 * 300)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


PNG_B64 = base64.b64encode(make_png()).decode()


def api_payload(**overrides) -> dict:
    data = {
        "title": "Landslide blocks mountain highway",
        "description": "Landslide on NH-5 near Dehradun; traffic halted in both directions.",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "reporter_id": "highway-patrol",
        "disaster_type": "landslide",
        "severity": 6.5,
        "latitude": 30.3165,
        "longitude": 78.0322,
        "location_name": "NH-5 Dehradun",
        "district": "Dehradun",
        "state": "Uttarakhand",
    }
    data.update(overrides)
    return data


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def clean_disaster_tables():
    """Ensure a pristine disaster-dataset before and after each test."""
    await init_db()
    from business_twin_ai.database import async_session_factory

    async with async_session_factory() as session:
        for model in (DisasterReport, IncidentCluster, ReporterProfile):
            from sqlalchemy import delete

            await session.execute(delete(model))
        await session.commit()
    yield
    async with async_session_factory() as session:
        from sqlalchemy import delete

        for model in (DisasterReport, IncidentCluster, ReporterProfile):
            await session.execute(delete(model))
        await session.commit()


async def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/disaster/reports — via the ValidationMiddleware
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_post_report_via_middleware():
    async with await client() as c:
        r = await c.post("/api/v1/disaster/reports", json=api_payload())
    assert r.status_code == 201
    body = r.json()
    assert "report_id" in body
    v = body["validation"]
    assert v["valid"] is True
    assert v["confidence_score"] > 50
    assert v["cluster_id"] is not None
    assert v["warning_level"] in ("GREEN", "YELLOW", "ORANGE", "RED")


@pytest.mark.asyncio
async def test_post_report_invalid_location_422():
    async with await client() as c:
        r = await c.post(
            "/api/v1/disaster/reports",
            json=api_payload(latitude=0.0, longitude=0.0),
        )
    assert r.status_code == 422
    body = r.json()
    assert body["validation"]["location"]["valid_location"] is False


@pytest.mark.asyncio
async def test_post_report_missing_required_field_422():
    async with await client() as c:
        bad = api_payload()
        del bad["disaster_type"]
        r = await c.post("/api/v1/disaster/reports", json=bad)
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/disaster/validate-report — pipeline without storage
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_validate_report_no_storage():
    async with await client() as c:
        r = await c.post("/api/v1/disaster/validate-report", json=api_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["validation"]["valid"] is True

    # Nothing stored.
    from business_twin_ai.database import async_session_factory

    async with async_session_factory() as session:
        from sqlalchemy import select

        count = (await session.execute(select(DisasterReport))).scalars().all()
        assert len(count) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# GET endpoints (spec §14)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_report_validation_retrieval():
    async with await client() as c:
        created = await c.post("/api/v1/disaster/reports", json=api_payload())
        report_id = created.json()["report_id"]
        r = await c.get(f"/api/v1/disaster/report/{report_id}/validation")
    assert r.status_code == 200
    body = r.json()
    assert body["report_id"] == report_id
    assert body["validation"]["confidence_score"] > 50


@pytest.mark.asyncio
async def test_clusters_endpoints():
    async with await client() as c:
        for i in range(3):
            await c.post(
                "/api/v1/disaster/reports",
                json=api_payload(reporter_id=f"user-{i}", latitude=30.3165 + i * 0.001),
            )
        clusters = await c.get("/api/v1/disaster/clusters")
        assert clusters.status_code == 200
        data = clusters.json()
        assert len(data) == 1
        cid = data[0]["cluster_id"]

        detail = await c.get(f"/api/v1/disaster/clusters/{cid}")
        assert detail.status_code == 200
        assert detail.json()["cluster"]["report_count"] == 3
        assert len(detail.json()["reports"]) == 3


@pytest.mark.asyncio
async def test_duplicates_and_suspicious_endpoints():
    async with await client() as c:
        # Two identical reports → duplicate; one spam bot → suspicious.
        await c.post("/api/v1/disaster/reports", json=api_payload(reporter_id="a"))
        await c.post("/api/v1/disaster/reports", json=api_payload(reporter_id="b"))
        await c.post(
            "/api/v1/disaster/reports",
            json=api_payload(
                reporter_id="bot",
                latitude=30.0,  # rounded grid coordinates → suspicious
                longitude=78.0,
                title="Win a free prize!!!",
                description="Click here to claim your free prize and win cash rewards now!!!",
            ),
        )

        dups = await c.get("/api/v1/disaster/reports/duplicates")
        assert dups.status_code == 200
        dup_ids = [d["id"] for d in dups.json()]
        assert len(dup_ids) == 1  # the second identical report

        sus = await c.get("/api/v1/disaster/reports/suspicious")
        assert sus.status_code == 200
        assert len(sus.json()) >= 1


@pytest.mark.asyncio
async def test_map_warnings_endpoint():
    async with await client() as c:
        for i in range(22):
            await c.post(
                "/api/v1/disaster/reports",
                json=api_payload(
                    reporter_id=f"crowd-{i}",
                    severity=8.5 + (i % 3) * 0.4,
                    latitude=26.85 + (i % 3) * 0.002,
                    longitude=80.95 + (i % 2) * 0.002,
                ),
            )
        r = await c.get("/api/v1/disaster/map/warnings")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["RED"] >= 1
    red = [w for w in body["warnings"] if w["warning_level"] == "RED"]
    assert red and red[0]["active_reports"] >= 20


# ═══════════════════════════════════════════════════════════════════════════════
# Existing endpoints still work (spec §14 — do not break anything)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_existing_health_endpoint_untouched():
    async with await client() as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_route_handler_without_middleware():
    """The documented route handler must work standalone (middleware bypassed)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from business_twin_ai.database import Base
    from business_twin_ai.disaster.api.routes.reports import create_report
    from business_twin_ai.disaster.schemas.schemas import DisasterReportCreate

    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        resp = await create_report(DisasterReportCreate(**api_payload()), session)
        assert resp.report_id
        assert resp.validation.valid is True

    # Invalid location raises 422 via HTTPException with the validation payload.
    from fastapi import HTTPException

    async with factory() as session:
        with pytest.raises(HTTPException) as exc:
            await create_report(
                DisasterReportCreate(**api_payload(latitude=0.0, longitude=0.0)), session
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["location"]["valid_location"] is False


@pytest.mark.asyncio
async def test_report_with_image_accepted():
    async with await client() as c:
        r = await c.post(
            "/api/v1/disaster/reports",
            json=api_payload(image_base64=PNG_B64),
        )
    assert r.status_code == 201
    v = r.json()["validation"]
    assert v["image"]["image_valid"] is True
    assert v["image"]["image_score"] >= 85
