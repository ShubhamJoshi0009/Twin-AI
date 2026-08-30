"""Unit tests for the disaster report validation stages and heuristics."""

from __future__ import annotations

import base64
import struct
import uuid
import zlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from business_twin_ai.database import Base
from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.models import DisasterReport
from business_twin_ai.disaster.utils.geo import (
    decimal_places,
    haversine_km,
    is_origin,
    is_valid_gps,
    precision_score,
)
from business_twin_ai.disaster.utils.images import inspect_image
from business_twin_ai.disaster.utils.text import (
    find_spam_words,
    repeated_char_ratio,
    text_similarity,
)
from business_twin_ai.disaster.validation.base import StageContext
from business_twin_ai.disaster.validation.confidence import ConfidenceStage
from business_twin_ai.disaster.validation.duplicates import DuplicateDetectionStage
from business_twin_ai.disaster.validation.image import ImageValidationStage
from business_twin_ai.disaster.validation.location import LocationValidationStage
from business_twin_ai.disaster.validation.metadata import MetadataValidationStage
from business_twin_ai.disaster.validation.suspicious import SuspiciousDetectionStage


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_png(width: int = 800, height: int = 600) -> bytes:
    """Build a small but structurally valid PNG in pure Python."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" + b"\x00\x00\x00" * width * height)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_jpeg_with_exif() -> bytes:
    """Build a minimal JPEG whose APP1 segment carries EXIF GPS + timestamp.

    TIFF layout (little-endian), offsets relative to TIFF start:
        0..8    TIFF header (II, 42, IFD0 offset = 8)
        8..26   IFD0: 1 entry (GPS IFD pointer 0x8825 -> 26)
        26..80  GPS IFD: 4 entries (ref/lat/ref/lon) + next-IFD pointer
        80..104 lat rationals (3 x RATIONAL)
        104..128 lon rationals (3 x RATIONAL)
    """
    def entry(tag: int, typ: int, count: int, value: int) -> bytes:
        return struct.pack("<HHII", tag, typ, count, value)

    def rat(value: float) -> bytes:
        return struct.pack("<II", int(value * 1000), 1000)

    gps_ifd_offset = 26
    lat_offset = 80
    lon_offset = 104

    ifd0 = (
        struct.pack("<H", 1)
        + entry(0x8825, 4, 1, gps_ifd_offset)
        + b"\x00" * 4  # next IFD
    )
    gps_ifd = (
        struct.pack("<H", 4)
        + entry(1, 2, 2, 0x4E)  # GPSLatitudeRef "N\x00\x00\x00" inline
        + entry(2, 5, 3, lat_offset)
        + entry(3, 2, 2, 0x45)  # GPSLongitudeRef "E\x00\x00\x00" inline
        + entry(4, 5, 3, lon_offset)
        + b"\x00" * 4  # next IFD
    )
    rationals = (
        rat(28) + rat(36) + rat(50.04)
        + rat(77) + rat(12) + rat(32.4)
    )

    tiff = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    tiff += ifd0
    tiff += b"\x00" * (gps_ifd_offset - len(tiff)) + gps_ifd
    tiff += b"\x00" * (lat_offset - len(tiff)) + rationals

    app1_payload = b"Exif\x00\x00" + tiff
    app1 = b"\xff\xe1" + struct.pack(">H", len(app1_payload) + 2) + app1_payload
    # SOF0 so dimensions are readable: height=100, width=256, 1 component.
    sof0 = b"\xff\xc0\x00\x0b\x08" + struct.pack(">HH", 100, 256) + b"\x01\x01\x11\x00"
    return b"\xff\xd8" + app1 + sof0 + b"\xff\xd9"


@pytest.fixture
async def db_session():
    """In-memory SQLite async session (mirrors the codebase convention)."""
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


def base_payload(**overrides) -> dict:
    payload = {
        "title": "Flooding in North District",
        "description": "Heavy rain has caused flooding in residential areas; several streets are underwater.",
        "timestamp": datetime.now(timezone.utc) - timedelta(minutes=30),
        "reporter_id": "reporter-1",
        "disaster_type": "flood",
        "severity": 6.0,
        "latitude": 28.6139,
        "longitude": 77.2095,
        "location_name": "North District",
        "district": "Central",
        "state": "Delhi",
    }
    payload.update(overrides)
    return payload


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Location validation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_location_valid():
    stage = LocationValidationStage()
    result = await stage.run(StageContext(payload=base_payload()))
    assert result.valid_location is True
    assert result.location_verified is True
    assert result.precision_score >= 80


@pytest.mark.asyncio
async def test_location_out_of_range():
    stage = LocationValidationStage()
    result = await stage.run(
        StageContext(payload=base_payload(latitude=95.0, longitude=77.0))
    )
    assert result.valid_location is False
    assert result.reason == "Coordinates outside allowed range"


@pytest.mark.asyncio
async def test_location_origin():
    stage = LocationValidationStage()
    result = await stage.run(
        StageContext(payload=base_payload(latitude=0.0, longitude=0.0))
    )
    assert result.valid_location is False
    assert "0,0" in result.reason


@pytest.mark.asyncio
async def test_location_missing():
    stage = LocationValidationStage()
    result = await stage.run(StageContext(payload=base_payload(latitude=None)))
    assert result.valid_location is False


def test_geo_helpers():
    assert is_valid_gps(28.6, 77.2, ValidationConfig()) is True
    assert is_valid_gps(91.0, 77.2, ValidationConfig()) is False
    assert is_valid_gps(None, 77.2, ValidationConfig()) is False
    assert is_origin(0.0, 0.0, ValidationConfig()) is True
    assert is_origin(28.6, 77.2, ValidationConfig()) is False
    # ~111 km per degree of latitude
    assert haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.19, rel=0.01)
    # 4 decimal places on both coordinates → high precision
    assert precision_score(28.6139, 77.2095, ValidationConfig()) >= 80
    assert decimal_places(28.6139) == 4
    assert decimal_places(77.209) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Metadata validation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_metadata_valid():
    stage = MetadataValidationStage()
    result = await stage.run(StageContext(payload=base_payload()))
    assert result.metadata_score >= 90
    assert result.valid is True


@pytest.mark.asyncio
async def test_metadata_missing_required():
    stage = MetadataValidationStage()
    payload = base_payload()
    del payload["disaster_type"]
    result = await stage.run(StageContext(payload=payload))
    assert result.metadata_score < 100
    assert any("disaster_type" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_metadata_future_timestamp():
    stage = MetadataValidationStage()
    future = datetime.now(timezone.utc) + timedelta(days=1)
    result = await stage.run(
        StageContext(payload=base_payload(timestamp=future))
    )
    assert any("future" in w for w in result.warnings)
    assert result.metadata_score < 100


@pytest.mark.asyncio
async def test_metadata_short_and_spam():
    stage = MetadataValidationStage()
    result = await stage.run(
        StageContext(
            payload=base_payload(title="Urgent!! claim your free prize now!!!", description="hi")
        )
    )
    assert result.metadata_score < 70
    assert any("spam" in w for w in result.warnings)


def test_text_helpers():
    assert text_similarity("flood in delhi", "flood in delhi") == pytest.approx(1.0)
    assert text_similarity("flood in delhi", "earthquake in nepal") < 0.5
    assert repeated_char_ratio("aaaaaa") == 1.0
    assert repeated_char_ratio("aabbccddeeff") == 0.0  # no run of 4+
    # "aaaa" is a 4-char run inside a 12-char string
    assert repeated_char_ratio("aabbaaaabbaa") == pytest.approx(4 / 12)
    assert find_spam_words("free prize winner!", ValidationConfig().SPAM_WORDS)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Image validation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_image_valid_png():
    stage = ImageValidationStage()
    b64 = base64.b64encode(make_png()).decode()
    result = await stage.run(StageContext(payload={"image_base64": b64}))
    assert result.image_valid is True
    assert result.image_score >= 90
    assert result.image_metadata["format"] == "png"
    assert result.image_metadata["width"] == 800
    assert result.image_hash


@pytest.mark.asyncio
async def test_image_missing_reduces_confidence_not_rejects():
    stage = ImageValidationStage()
    result = await stage.run(StageContext(payload={}))
    assert result.image_valid is True
    assert result.image_score == 50.0  # neutral — halves the image component


@pytest.mark.asyncio
async def test_image_corrupt():
    stage = ImageValidationStage()
    b64 = base64.b64encode(b"this is not an image at all").decode()
    result = await stage.run(StageContext(payload={"image_base64": b64}))
    assert result.image_valid is False
    assert result.image_score < 60


@pytest.mark.asyncio
async def test_image_bad_base64():
    stage = ImageValidationStage()
    result = await stage.run(StageContext(payload={"image_base64": "!!!not-base64!!!"}))
    assert result.image_valid is False


def test_image_inspector_png():
    info = inspect_image(make_png(320, 240))
    assert info.valid is True
    assert info.format == "png"
    assert (info.width, info.height) == (320, 240)
    assert len(info.sha256) == 64


def test_image_inspector_jpeg_exif():
    info = inspect_image(make_jpeg_with_exif())
    assert info.valid is True
    assert info.format == "jpeg"
    assert info.gps is not None
    lat, lon = info.gps
    assert abs(lat - 28.6) < 0.1
    assert abs(lon - 77.2) < 0.1


def test_image_inspector_unknown_format():
    info = inspect_image(b"\x00\x01\x02\x03 garbage bytes")
    assert info.valid is False
    assert info.corruption_reason == "unrecognized format"


def test_image_inspector_truncated_exif_does_not_crash():
    """Malformed/truncated EXIF must degrade to corruption, never raise."""
    # A JPEG APP1 that starts like EXIF but is cut off mid-TIFF.
    truncated = (
        b"\xff\xd8"
        + b"\xff\xe1\x00\x20Exif\x00\x00II"
        + b"\x2a\x00\x08\x00\x00\x00"  # TIFF header claims IFD at 8
        + b"\xff\xc0\x00\x0b\x08" + struct.pack(">HH", 10, 10) + b"\x01\x01\x11\x00"
        + b"\xff\xd9"
    )
    info = inspect_image(truncated)  # must not raise
    assert info.format == "jpeg"
    assert info.gps is None


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Duplicate detection
# ═══════════════════════════════════════════════════════════════════════════════

async def _seed_report(session: AsyncSession, **overrides) -> DisasterReport:
    data = base_payload(**overrides)
    report = DisasterReport(
        id=uuid.uuid4(),
        title=data["title"],
        description=data["description"],
        timestamp=data["timestamp"],
        reporter_id=data["reporter_id"],
        disaster_type=data["disaster_type"],
        severity=data["severity"],
        latitude=data["latitude"],
        longitude=data["longitude"],
        location_name=data["location_name"],
        district=data["district"],
        state=data["state"],
    )
    session.add(report)
    await session.flush()
    return report


@pytest.mark.asyncio
async def test_duplicate_detected(db_session: AsyncSession):
    await _seed_report(db_session, reporter_id="other-reporter")
    stage = DuplicateDetectionStage()
    result = await stage.run(
        StageContext(payload=base_payload(), db=db_session, config=ValidationConfig())
    )
    assert result.duplicate is True
    assert result.duplicate_score > 85
    assert result.duplicate_of is not None


@pytest.mark.asyncio
async def test_no_duplicate_far_away(db_session: AsyncSession):
    await _seed_report(
        db_session,
        reporter_id="other-reporter",
        latitude=35.6895,  # Tokyo — thousands of km away
        longitude=139.6917,
        description="A completely different earthquake report from another city.",
    )
    stage = DuplicateDetectionStage()
    result = await stage.run(
        StageContext(payload=base_payload(), db=db_session, config=ValidationConfig())
    )
    assert result.duplicate is False
    assert result.duplicate_score < 60


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Suspicious detection
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_suspicious_future_timestamp():
    stage = SuspiciousDetectionStage()
    future = datetime.now(timezone.utc) + timedelta(days=2)
    result = await stage.run(
        StageContext(payload=base_payload(timestamp=future))
    )
    assert result.suspicious is True
    assert any("future" in r for r in result.reasons)


@pytest.mark.asyncio
async def test_suspicious_flooding(db_session: AsyncSession):
    for i in range(12):
        await _seed_report(
            db_session,
            reporter_id="spammer",
            description=f"Report number {i} about flooding in the same area.",
        )
    stage = SuspiciousDetectionStage()
    ctx = StageContext(payload=base_payload(reporter_id="spammer"), db=db_session)
    ctx.results = {"metadata": type("M", (), {"metadata_score": 90})(), "image": None}
    result = await stage.run(ctx)
    assert result.suspicious is True
    assert any("flooding" in r for r in result.reasons)


@pytest.mark.asyncio
async def test_suspicious_copied_description(db_session: AsyncSession):
    original = base_payload(reporter_id="legit-user")
    await _seed_report(db_session, reporter_id="legit-user")
    stage = SuspiciousDetectionStage()
    ctx = StageContext(payload=original, db=db_session)
    ctx.results = {"metadata": type("M", (), {"metadata_score": 90})(), "image": None}
    result = await stage.run(ctx)
    # Exact copy from a different reporter.
    assert result.suspicious is True
    assert any("copied" in r for r in result.reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Confidence scoring
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_confidence_high_for_good_report():
    stage = ConfidenceStage()
    ctx = StageContext(payload=base_payload())
    ctx.results = {
        "location": type("L", (), {"location_score": 95})(),
        "metadata": type("M", (), {"metadata_score": 90})(),
        "image": type("I", (), {"image_score": 92})(),
        "duplicate": type("D", (), {"duplicate_score": 10})(),
    }
    result = await stage.run(ctx)
    # 0.30*95 + 0.20*90 + 0.20*92 + 0.15*90 + 0.15*50 ≈ 86.5
    assert 80 <= result.confidence_score <= 95


@pytest.mark.asyncio
async def test_confidence_low_for_bad_report():
    stage = ConfidenceStage()
    ctx = StageContext(payload=base_payload())
    ctx.results = {
        "location": type("L", (), {"location_score": 30})(),
        "metadata": type("M", (), {"metadata_score": 20})(),
        "image": type("I", (), {"image_score": 10})(),
        "duplicate": type("D", (), {"duplicate_score": 90})(),
    }
    result = await stage.run(ctx)
    assert result.confidence_score < 50
