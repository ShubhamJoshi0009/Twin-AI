"""Tests for the demo-data seeder (business_twin_ai/seed.py)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from business_twin_ai.database import Base
from business_twin_ai.core.models.database import DigitalTwin, Insight, Simulation
from business_twin_ai.seed import load_custom_data, seed_database
from business_twin_ai.supply_chain.models.database import (
    InventoryItem,
    Shipment,
    Supplier,
    Warehouse,
)

CUSTOM_DATA = {
    "business": {
        "name": "Custom Corp",
        "industry": "retail",
        "revenue": 1_000_000,
        "expenses": 700_000,
        "customers": 500,
        "employees": 40,
        "sales": 900_000,
        "marketing_budget": 80_000,
        "market_share": 4.0,
    },
    "simulations": [
        {
            "decision_type": "increase_price",
            "decision_params": {"percent": 5},
            "predicted_revenue": 1_050_000,
            "predicted_profit": 330_000,
            "confidence_score": 71.0,
        }
    ],
    "supply_chain": {
        "suppliers": [
            {
                "name": "Custom Supplier",
                "location": "Austin, TX",
                "country": "USA",
                "product_categories": ["components"],
                "lead_time_days": 3,
                "cost_per_unit": 10.0,
                "capacity": 5000,
                "quality_rating": 4.6,
            }
        ],
        "warehouses": [
            {"name": "Custom Warehouse", "location": "Austin, TX", "capacity": 20000}
        ],
        "inventory": [
            {
                "product_name": "Custom Widget",
                "product_sku": "CW-001",
                "category": "components",
                "current_stock": 300,
                "reorder_level": 100,
                "safety_stock": 50,
                "max_stock": 2000,
                "unit_cost": 12.0,
            }
        ],
        "shipments": [
            {
                "shipment_number": "SHP-CUSTOM-1",
                "product_name": "Custom Widget",
                "quantity": 100,
                "origin": "Austin, TX",
                "destination": "Dallas, TX",
                "distance_km": 300,
                "fuel_cost": 50.0,
                "transport_cost": 180.0,
                "status": "in_transit",
            }
        ],
    },
}


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


async def _counts(db: AsyncSession) -> dict:
    async def count(model):
        return (await db.execute(select(func.count()).select_from(model))).scalar() or 0

    return {
        "twins": await count(DigitalTwin),
        "simulations": await count(Simulation),
        "insights": await count(Insight),
        "suppliers": await count(Supplier),
        "warehouses": await count(Warehouse),
        "inventory": await count(InventoryItem),
        "shipments": await count(Shipment),
    }


@pytest.mark.asyncio
async def test_seed_populates_all_entities(db_session: AsyncSession):
    """Seeding creates a twin, simulations, insights, and full supply chain."""
    summary = await seed_database(db_session, force=True)

    assert summary["skipped"] is False
    assert summary["twin"]["name"] == "TechNova Solutions"

    counts = await _counts(db_session)
    assert counts["twins"] == 1
    assert counts["simulations"] == 3
    assert counts["insights"] == 3
    assert counts["suppliers"] == 5
    assert counts["warehouses"] == 3
    assert counts["inventory"] == 5
    assert counts["shipments"] == 4


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session: AsyncSession):
    """A second seed on a populated DB is skipped (no duplicates)."""
    await seed_database(db_session, force=True)
    summary = await seed_database(db_session)

    assert summary["skipped"] is True
    counts = await _counts(db_session)
    assert counts["twins"] == 1
    assert counts["suppliers"] == 5


@pytest.mark.asyncio
async def test_seed_force_reseeds(db_session: AsyncSession):
    """--force wipes existing demo data and reseeds cleanly."""
    await seed_database(db_session, force=True)
    # Simulate drift: add a second twin on top of the seeded data.
    db_session.add(DigitalTwin(name="Drift Corp", industry="general"))
    await db_session.flush()

    summary = await seed_database(db_session, force=True)
    assert summary["skipped"] is False

    counts = await _counts(db_session)
    assert counts["twins"] == 1  # drift twin removed
    assert counts["suppliers"] == 5


@pytest.mark.asyncio
async def test_seed_with_custom_data(db_session: AsyncSession, tmp_path):
    """A custom JSON file overrides the demo dataset with user-specific data."""
    custom_file = tmp_path / "custom.json"
    custom_file.write_text(json.dumps(CUSTOM_DATA), encoding="utf-8")

    summary = await seed_database(db_session, force=True, custom_file=str(custom_file))

    assert summary["skipped"] is False
    assert summary["twin"]["name"] == "Custom Corp"

    counts = await _counts(db_session)
    assert counts["twins"] == 1
    assert counts["simulations"] == 1
    assert counts["suppliers"] == 1
    assert counts["warehouses"] == 1
    assert counts["inventory"] == 1
    assert counts["shipments"] == 1

    # Derived metrics are still computed from custom inputs.
    twin = (await db_session.execute(select(DigitalTwin))).scalar_one()
    assert twin.profit == 300_000  # revenue - expenses
    assert twin.kpis["profit_margin"] == 30.0


def test_load_custom_data_bare_business(tmp_path):
    """A bare business JSON object is accepted (wrapped as 'business')."""
    f = tmp_path / "bare.json"
    f.write_text(json.dumps({"name": "Bare Corp", "revenue": 100}), encoding="utf-8")
    loaded = load_custom_data(f)
    assert loaded["business"]["name"] == "Bare Corp"
    assert loaded["simulations"] == []
    assert loaded["supply_chain"] == {}


def test_load_custom_data_missing_file(tmp_path):
    """A missing custom data file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_custom_data(tmp_path / "nope.json")
