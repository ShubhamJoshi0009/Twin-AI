"""Unit tests for the Digital Twin engine."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from business_twin_ai.database import Base
from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.schemas.schemas import BusinessData


@pytest.fixture
async def db_session():
    """Create an in-memory SQLite async session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def sample_data() -> BusinessData:
    """Sample business data for tests."""
    return BusinessData(
        name="Test Corp",
        industry="technology",
        revenue=1_000_000,
        expenses=700_000,
        customers=200,
        employees=50,
        sales=900_000,
        marketing_budget=100_000,
        market_share=5.0,
    )


@pytest.mark.asyncio
async def test_create_twin(db_session: AsyncSession, sample_data: BusinessData):
    """Test creating a digital twin."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(sample_data)

    assert twin.name == "Test Corp"
    assert twin.industry == "technology"
    assert twin.revenue == 1_000_000
    assert twin.profit == 300_000  # revenue - expenses
    assert twin.id is not None


@pytest.mark.asyncio
async def test_get_twin(db_session: AsyncSession, sample_data: BusinessData):
    """Test retrieving a digital twin."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(sample_data)

    fetched = await engine.get_twin(twin.id)
    assert fetched is not None
    assert fetched.name == "Test Corp"
    assert fetched.revenue == 1_000_000


@pytest.mark.asyncio
async def test_get_nonexistent_twin(db_session: AsyncSession):
    """Test retrieving a non-existent twin returns None."""
    engine = DigitalTwinEngine(db_session)
    result = await engine.get_twin(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_update_twin(db_session: AsyncSession, sample_data: BusinessData):
    """Test updating a digital twin."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(sample_data)

    update_data = BusinessData(
        name="Test Corp",
        industry="technology",
        revenue=1_500_000,
        expenses=800_000,
        customers=300,
        employees=60,
        sales=1_400_000,
        marketing_budget=150_000,
        market_share=7.5,
    )

    updated = await engine.update_twin(twin.id, update_data)
    assert updated is not None
    assert updated.revenue == 1_500_000
    assert updated.profit == 700_000
    assert updated.customers == 300


@pytest.mark.asyncio
async def test_delete_twin(db_session: AsyncSession, sample_data: BusinessData):
    """Test deleting a digital twin."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(sample_data)

    deleted = await engine.delete_twin(twin.id)
    assert deleted is True

    fetched = await engine.get_twin(twin.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_list_twins(db_session: AsyncSession, sample_data: BusinessData):
    """Test listing digital twins."""
    engine = DigitalTwinEngine(db_session)
    await engine.create_twin(sample_data)

    # Create a second twin
    data2 = BusinessData(name="Another Corp", industry="finance", revenue=2_000_000, expenses=1_000_000)
    await engine.create_twin(data2)

    twins = await engine.list_twins()
    assert len(twins) == 2


@pytest.mark.asyncio
async def test_kpi_computation(db_session: AsyncSession, sample_data: BusinessData):
    """Test that KPIs are computed correctly."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(sample_data)

    kpis = twin.kpis
    assert kpis is not None
    assert "profit_margin" in kpis
    assert "revenue_per_employee" in kpis
    assert "marketing_roi" in kpis
    assert kpis["profit_margin"] == 30.0  # 300k / 1M * 100
    assert kpis["revenue_per_employee"] == 20_000  # 1M / 50
    assert kpis["marketing_roi"] == 9.0  # 900k / 100k


@pytest.mark.asyncio
async def test_get_twin_state(db_session: AsyncSession, sample_data: BusinessData):
    """Test extracting twin state as dictionary."""
    engine = DigitalTwinEngine(db_session)
    twin = await engine.create_twin(sample_data)

    state = engine.get_twin_state(twin)
    assert isinstance(state, dict)
    assert state["name"] == "Test Corp"
    assert state["revenue"] == 1_000_000
    assert state["customers"] == 200
