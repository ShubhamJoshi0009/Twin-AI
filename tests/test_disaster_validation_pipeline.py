"""Integration tests for the disaster report validation pipeline.

Covers the end-to-end flow: validation → storage → clustering → warning state
→ reporter trust, plus the spec §15 demo cases (genuine / duplicate / fake /
invalid-location / RED cluster).
"""

from __future__ import annotations

import base64
import struct
import uuid
import zlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from business_twin_ai.database import Base
from business_twin_ai.disaster.engines.clustering import ClusteringService
from business_twin_ai.disaster.engines.reporter_trust import ReporterTrustService
from business_twin_ai.disaster.engines.service import ValidationService
from business_twin_ai.disaster.engines.warning_state import MapWarningStateUpdater
from business_twin_ai.disaster.models import DisasterReport, IncidentCluster, ReporterProfile
from business_twin_ai.disaster.validation.pipeline import ValidationPipeline


def make_png() -> bytes:
    """Small valid PNG (shared with unit tests)."""

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


@pytest.fixture
async def db_session():
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


def payload(**overrides) -> dict:
    data = {
        "title": "Flash flood hits riverside colony",
        "description": "Riverside colony submerged after heavy rain; residents need evacuation.",
        "timestamp": datetime.now(timezone.utc) - timedelta(minutes=45),
        "reporter_id": "riverside-watch",
        "disaster_type": "flood",
        "severity": 7.0,
        "latitude": 28.6129,
        "longitude": 77.2295,
        "location_name": "Riverside Colony",
        "district": "Central",
        "state": "Delhi",
    }
    data.update(overrides)
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# Demo case 1: genuine report
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_genuine_report_stored_with_high_confidence(db_session: AsyncSession):
    service = ValidationService(db_session)
    outcome = await service.submit_report(payload())
    assert outcome.stored is True
    assert outcome.rejected is False
    assert outcome.validation["valid"] is True
    assert outcome.validation["confidence_score"] > 70
    assert outcome.validation["duplicate"] is False
    assert outcome.validation["suspicious"] is False
    assert outcome.validation["cluster_id"] is not None
    assert outcome.validation["warning_level"] in ("GREEN", "YELLOW", "ORANGE", "RED")

    stored = await db_session.get(DisasterReport, uuid.UUID(outcome.report_id))
    assert stored is not None
    assert stored.validation_status == "valid"
    assert stored.confidence_score == outcome.validation["confidence_score"]
    assert stored.location_score > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Demo case 2: duplicate report
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_duplicate_report_flagged_and_linked(db_session: AsyncSession):
    service = ValidationService(db_session)
    first = await service.submit_report(payload(reporter_id="user-a"))
    assert first.stored is True

    second = await service.submit_report(payload(reporter_id="user-b"))
    assert second.validation["duplicate"] is True
    assert second.validation["duplicate_score"] > 85
    assert second.validation["duplicate_details"]["duplicate_of"] == first.report_id
    # The duplicate joins the same cluster.
    assert second.validation["cluster_id"] == first.validation["cluster_id"]

    stored = await db_session.get(DisasterReport, uuid.UUID(second.report_id))
    assert stored.duplicate is True
    assert stored.duplicate_of == first.report_id
    assert stored.validation_status == "duplicate"


# ═══════════════════════════════════════════════════════════════════════════════
# Demo case 3: fake report with reused image
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fake_report_reused_image_flagged_suspicious(db_session: AsyncSession):
    service = ValidationService(db_session)
    await service.submit_report(payload(image_base64=PNG_B64))

    # Same image reused from a *different* location (so it is not a duplicate),
    # plus spam text — the report must be flagged as suspicious.
    fake = await service.submit_report(
        payload(
            reporter_id="bot-account",
            image_base64=PNG_B64,
            latitude=19.0760,   # Mumbai — far from the original Delhi report
            longitude=72.8777,
            title="Win a free prize now!!!",
            description="Click here to claim your free prize and win cash rewards instantly!!!",
        )
    )
    assert fake.validation["suspicious"] is True
    reasons = fake.validation["suspicious_details"]["reasons"]
    assert any("reused" in r for r in reasons)
    stored = await db_session.get(DisasterReport, uuid.UUID(fake.report_id))
    assert stored.suspicious is True
    assert stored.validation_status == "flagged"


# ═══════════════════════════════════════════════════════════════════════════════
# Demo case 4: invalid location report
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_invalid_location_report_rejected(db_session: AsyncSession):
    service = ValidationService(db_session)
    outcome = await service.submit_report(payload(latitude=0.0, longitude=0.0))
    assert outcome.rejected is True
    assert outcome.stored is False
    assert outcome.status_code == 422
    assert outcome.validation["location"]["valid_location"] is False

    # Out-of-range coordinates also rejected.
    outcome2 = await service.submit_report(payload(latitude=123.0, longitude=77.0))
    assert outcome2.rejected is True


# ═══════════════════════════════════════════════════════════════════════════════
# Clustering (spec §5)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cluster_creation_and_aggregation(db_session: AsyncSession):
    service = ValidationService(db_session)
    cluster_ids = set()
    for i in range(5):
        outcome = await service.submit_report(
            payload(
                reporter_id=f"user-{i}",
                latitude=28.61 + i * 0.001,
                longitude=77.22 + i * 0.001,
                severity=5.0 + i * 0.5,
            )
        )
        cluster_ids.add(outcome.validation["cluster_id"])
        await db_session.commit()

    assert len(cluster_ids) == 1
    cid = cluster_ids.pop()

    result = await db_session.execute(
        select(IncidentCluster).where(IncidentCluster.cluster_id == cid)
    )
    cluster = result.scalar_one()
    assert cluster.report_count == 5
    assert 5.0 <= cluster.average_severity <= 7.5


# ═══════════════════════════════════════════════════════════════════════════════
# Warning levels (spec §10)
# ═══════════════════════════════════════════════════════════════════════════════

def test_warning_level_transitions():
    updater = MapWarningStateUpdater()
    assert updater.compute_warning_level(2.0, 2) == "GREEN"      # severity<3, reports<3
    assert updater.compute_warning_level(5.0, 5) == "YELLOW"     # severity>=4, reports>=3
    assert updater.compute_warning_level(7.5, 12) == "ORANGE"    # severity>=7, reports>=10
    assert updater.compute_warning_level(9.0, 25) == "RED"       # severity>8, reports>20


@pytest.mark.asyncio
async def test_warning_level_escalates_with_reports(db_session: AsyncSession):
    service = ValidationService(db_session)
    last = None
    for i in range(22):  # build a RED cluster
        last = await service.submit_report(
            payload(
                reporter_id=f"crowd-{i}",
                latitude=26.85 + (i % 3) * 0.002,
                longitude=80.95 + (i % 2) * 0.002,
                severity=8.5 + (i % 3) * 0.4,
                disaster_type="flood",
            )
        )
        await db_session.commit()
    assert last.validation["warning_level"] == "RED"

    # Map endpoint state reflects it.
    updater = MapWarningStateUpdater()
    result = await db_session.execute(
        select(IncidentCluster).order_by(IncidentCluster.report_count.desc())
    )
    top = result.scalars().first()
    assert top.report_count == 22
    assert updater.compute_warning_level(top.average_severity, top.report_count) == "RED"


# ═══════════════════════════════════════════════════════════════════════════════
# Reporter trust (spec §8)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reporter_trust_updates(db_session: AsyncSession):
    service = ValidationService(db_session)
    trust = ReporterTrustService(db_session)

    # Five distinct, genuinely-accepted reports raise trust.
    descriptions = [
        "River overflowed the old bridge at dawn; two cars swept away.",
        "School roof collapsed in the west wing after heavy rain.",
        "Evacuation underway for elderly residents near the temple.",
        "Power lines down across the market square; crews dispatched.",
        "Landslide blocked the main road; ambulances rerouted via bypass.",
    ]
    for i, desc in enumerate(descriptions):
        await service.submit_report(
            payload(
                reporter_id="good-reporter",
                title=f"Incident report {i + 1}",
                description=desc,
                latitude=28.6139 + i * 0.05,
                longitude=77.2095 + i * 0.05,
            )
        )
        await db_session.commit()
    profile = await trust.get("good-reporter")
    assert profile is not None
    assert profile.reporter_trust_score > 50
    assert profile.accepted_reports == 5

    # Fake spam reports tank trust.
    for _ in range(5):
        await service.submit_report(
            payload(
                reporter_id="bad-reporter",
                title="Urgent!! free prize winner!!!",
                description="Click here to claim your exclusive offer and win cash reward now!!!",
            )
        )
        await db_session.commit()
    bad = await trust.get("bad-reporter")
    assert bad is not None
    assert bad.reporter_trust_score < 50
    assert bad.false_reports >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline validation-only mode
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_validate_only_does_not_store(db_session: AsyncSession):
    service = ValidationService(db_session)
    validation = await service.validate_only(payload())
    assert validation["valid"] is True
    assert validation["confidence_score"] > 0
    assert validation["report_id"] is not None
    stored = await db_session.get(DisasterReport, uuid.UUID(validation["report_id"]))
    assert stored is None

    # Validate-only must not persist any side effects (e.g. reporter profiles).
    profiles = (await db_session.execute(select(ReporterProfile))).scalars().all()
    assert len(profiles) == 0


@pytest.mark.asyncio
async def test_pipeline_execution_time_budget(db_session: AsyncSession):
    """Validation of a normal report must complete quickly (< 200ms budget)."""
    import time

    pipeline = ValidationPipeline()
    start = time.perf_counter()
    result = await pipeline.run(payload(), db=db_session)
    elapsed = (time.perf_counter() - start) * 1000
    assert result.valid is True
    assert elapsed < 200, f"pipeline took {elapsed:.1f}ms"
