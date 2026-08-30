"""Unit tests for the Supply Chain Warehouse engine.

Covers ``update_utilization`` (efficiency scoring) and ``get_utilization_report``
(trend classification + recommendations) across the capacity bands that the
API integration tests only partially touch.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from business_twin_ai.database import Base
from business_twin_ai.supply_chain.engines.warehouse import WarehouseEngine
from business_twin_ai.supply_chain.models.database import InventoryItem, Warehouse
from business_twin_ai.supply_chain.schemas.schemas import WarehouseCreate


@pytest.fixture
async def db_session():
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


async def _make_warehouse(db: AsyncSession, capacity: int = 10_000, cost: float = 1.0) -> Warehouse:
    engine = WarehouseEngine(db)
    wh = await engine.create_warehouse(
        WarehouseCreate(name="DC-1", location="Newark, NJ", capacity=capacity, storage_cost_per_unit=cost)
    )
    await db.commit()
    return wh


async def _add_stock(db: AsyncSession, warehouse_id: uuid.UUID, stock: int, sku: str = "SKU-1") -> None:
    db.add(
        InventoryItem(
            warehouse_id=warehouse_id,
            product_name=f"Product {sku}",
            product_sku=sku,
            current_stock=stock,
        )
    )
    await db.flush()


@pytest.mark.asyncio
async def test_create_and_get_warehouse(db_session: AsyncSession) -> None:
    engine = WarehouseEngine(db_session)
    wh = await engine.create_warehouse(
        WarehouseCreate(name="DC-A", location="Austin, TX", capacity=20_000, storage_cost_per_unit=0.5)
    )
    await db_session.commit()

    fetched = await engine.get_warehouse(wh.id)
    assert fetched is not None
    assert fetched.name == "DC-A"

    assert await engine.get_warehouse(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_list_warehouses_active_only(db_session: AsyncSession) -> None:
    engine = WarehouseEngine(db_session)
    active = await _make_warehouse(db_session)
    inactive = await _make_warehouse(db_session)
    inactive.is_active = False
    await db_session.commit()

    listed = await engine.list_warehouses()
    ids = {w.id for w in listed}
    assert active.id in ids
    assert inactive.id not in ids


@pytest.mark.asyncio
async def test_update_utilization_empty_warehouse(db_session: AsyncSession) -> None:
    """Zero stock → 0% utilization and a neutral efficiency score."""
    wh = await _make_warehouse(db_session, capacity=10_000)
    engine = WarehouseEngine(db_session)
    updated = await engine.update_utilization(wh.id)
    assert updated is not None
    assert updated.utilization == 0.0
    assert updated.efficiency_score == 50.0

    assert await engine.update_utilization(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_update_utilization_partial(db_session: AsyncSession) -> None:
    """7,500/10,000 → 75% utilization → best efficiency (100)."""
    wh = await _make_warehouse(db_session, capacity=10_000)
    await _add_stock(db_session, wh.id, 7_500)
    await db_session.commit()

    updated = await WarehouseEngine(db_session).update_utilization(wh.id)
    assert updated.utilization == 75.0
    assert updated.efficiency_score == 100.0


@pytest.mark.asyncio
async def test_update_utilization_zero_capacity(db_session: AsyncSession) -> None:
    """Capacity 0 must not divide by zero."""
    wh = await _make_warehouse(db_session, capacity=0)
    await _add_stock(db_session, wh.id, 500)
    await db_session.commit()

    updated = await WarehouseEngine(db_session).update_utilization(wh.id)
    assert updated.utilization == 0.0


@pytest.mark.asyncio
async def test_utilization_report_overloaded(db_session: AsyncSession) -> None:
    """95% utilization → 'overloaded' trend + near-capacity recommendation."""
    wh = await _make_warehouse(db_session, capacity=10_000)
    await _add_stock(db_session, wh.id, 9_500)
    await db_session.commit()

    engine = WarehouseEngine(db_session)
    await engine.update_utilization(wh.id)
    report = await engine.get_utilization_report(wh.id)
    assert report is not None
    assert report.utilization_trend == "overloaded"
    assert report.current_utilization == 95.0
    assert any("near capacity" in r for r in report.recommendations)


@pytest.mark.asyncio
async def test_utilization_report_optimal(db_session: AsyncSession) -> None:
    """78% utilization → 'optimal' trend + positive recommendation."""
    wh = await _make_warehouse(db_session, capacity=10_000)
    await _add_stock(db_session, wh.id, 7_800)
    await db_session.commit()

    engine = WarehouseEngine(db_session)
    await engine.update_utilization(wh.id)
    report = await engine.get_utilization_report(wh.id)
    assert report.utilization_trend == "optimal"
    assert any("optimal utilization" in r for r in report.recommendations)
    assert report.storage_cost == 7800.0


@pytest.mark.asyncio
async def test_utilization_report_underutilized(db_session: AsyncSession) -> None:
    """40% utilization → 'underutilized' trend."""
    wh = await _make_warehouse(db_session, capacity=10_000)
    await _add_stock(db_session, wh.id, 4_000)
    await db_session.commit()

    engine = WarehouseEngine(db_session)
    await engine.update_utilization(wh.id)
    report = await engine.get_utilization_report(wh.id)
    assert report.utilization_trend == "underutilized"


@pytest.mark.asyncio
async def test_utilization_report_empty(db_session: AsyncSession) -> None:
    """10% utilization → 'empty' trend + consolidation recommendation."""
    wh = await _make_warehouse(db_session, capacity=10_000)
    await _add_stock(db_session, wh.id, 1_000)
    await db_session.commit()

    engine = WarehouseEngine(db_session)
    await engine.update_utilization(wh.id)
    report = await engine.get_utilization_report(wh.id)
    assert report.utilization_trend == "empty"
    assert any("underutilized" in r for r in report.recommendations)


@pytest.mark.asyncio
async def test_utilization_report_missing(db_session: AsyncSession) -> None:
    assert await WarehouseEngine(db_session).get_utilization_report(uuid.uuid4()) is None
