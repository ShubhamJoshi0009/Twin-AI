"""API tests for the seeding endpoints (Settings → Data & Seeding)."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

# Self-contained DB (mirrors the pattern of the other integration tests).
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_seed_api_{uuid.uuid4().hex[:8]}.db")
# This suite exercises the seed API itself — enable it explicitly (it is off
# by default in production).
os.environ.setdefault("ENABLE_SEED_API", "true")

from business_twin_ai.app import app  # noqa: E402

CUSTOM_DATA = {
    "business": {
        "name": "Uploaded Corp",
        "industry": "retail",
        "revenue": 500_000,
        "expenses": 300_000,
        "customers": 100,
        "employees": 20,
        "sales": 450_000,
        "marketing_budget": 50_000,
        "market_share": 3.0,
    },
    "supply_chain": {
        "suppliers": [
            {
                "name": "Uploaded Supplier",
                "location": "Austin, TX",
                "country": "USA",
                "product_categories": ["components"],
                "lead_time_days": 3,
                "cost_per_unit": 10.0,
                "capacity": 5000,
                "quality_rating": 4.5,
            }
        ],
        "warehouses": [{"name": "Uploaded Warehouse", "location": "Austin, TX", "capacity": 20000}],
    },
}


@pytest.fixture
def client():
    # Entering the context runs the lifespan: init_db + demo auto-seed.
    with TestClient(app) as c:
        yield c


def test_status_reports_seeded_data(client):
    r = client.get("/api/v1/system/seed/status")
    assert r.status_code == 200
    body = r.json()
    assert body["has_data"] is True
    assert body["twin_count"] >= 1


def test_apply_custom_payload(client):
    r = client.post("/api/v1/system/seed", json={"data": CUSTOM_DATA, "force": True})
    assert r.status_code == 200
    body = r.json()
    assert body["skipped"] is False
    assert body["twin"]["name"] == "Uploaded Corp"
    assert body["counts"]["suppliers"] == 1
    assert body["counts"]["warehouses"] == 1

    twins = client.get("/api/v1/digital-twins").json()
    assert len(twins) == 1
    assert twins[0]["name"] == "Uploaded Corp"

    status = client.get("/api/v1/system/seed/status").json()
    assert status["twin_count"] == 1


def test_apply_demo_dataset(client):
    r = client.post("/api/v1/system/seed", json={"data": None, "force": True})
    assert r.status_code == 200
    body = r.json()
    assert body["skipped"] is False
    assert body["twin"]["name"] == "TechNova Solutions"
    assert body["counts"]["suppliers"] == 5


def test_apply_skips_without_force_when_data_exists(client):
    # DB already has data (auto-seeded) → a non-forced seed is skipped safely.
    r = client.post("/api/v1/system/seed", json={"data": CUSTOM_DATA, "force": False})
    assert r.status_code == 200
    assert r.json()["skipped"] is True


def test_apply_invalid_business_data_returns_422(client):
    # Missing required "name" in the business section.
    r = client.post("/api/v1/system/seed", json={"data": {"business": {"revenue": 100}}, "force": True})
    assert r.status_code == 422


def test_apply_non_object_data_returns_422(client):
    r = client.post("/api/v1/system/seed", json={"data": ["not", "an", "object"], "force": True})
    assert r.status_code == 422


def test_apply_inventory_without_warehouse_returns_422(client):
    # Inventory needs at least one warehouse to attach to — this should be a
    # client error (422), not a 500.
    payload = {
        "business": {
            "name": "Incomplete Corp",
            "industry": "retail",
            "revenue": 100_000,
            "expenses": 80_000,
        },
        "supply_chain": {
            "inventory": [
                {
                    "product_name": "Orphan SKU",
                    "product_sku": "ORP-1",
                    "current_stock": 10,
                    "reorder_level": 5,
                    "safety_stock": 2,
                    "max_stock": 100,
                }
            ]
        },
    }
    r = client.post("/api/v1/system/seed", json={"data": payload, "force": True})
    assert r.status_code == 422
    assert "warehouse" in r.json()["detail"].lower()


def test_template_endpoint_returns_example(client):
    r = client.get("/api/v1/system/seed/template")
    assert r.status_code == 200
    body = r.json()
    assert "business" in body
    assert body["business"]["name"] == "GreenLeaf Organics"
    assert "supply_chain" in body
