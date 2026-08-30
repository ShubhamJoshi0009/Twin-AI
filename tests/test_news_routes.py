"""Tests for the real-time news API and Route Diversion Simulator."""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_news_{uuid.uuid4().hex[:8]}.db")


def test_market_news_endpoint_returns_headlines() -> None:
    """GET /api/v1/news returns normalized headlines (curated fallback offline)."""
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    with TestClient(app) as client:
        r = client.get("/api/v1/news", params={"q": "red sea shipping", "limit": 4})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert 1 <= len(data) <= 4
        item = data[0]
        assert item["title"]
        assert item["source"]
        assert item["url"]


def test_market_news_requires_query() -> None:
    """Missing query returns 422."""
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    with TestClient(app) as client:
        r = client.get("/api/v1/news")
        assert r.status_code == 422


def test_route_network_endpoint() -> None:
    """GET /supply-chain/routes/network exposes ports, segments and chokepoints."""
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    with TestClient(app) as client:
        r = client.get("/api/v1/supply-chain/routes/network")
        assert r.status_code == 200
        data = r.json()
        assert len(data["ports"]) >= 20
        assert len(data["segments"]) >= 30
        ids = {cp["id"] for cp in data["chokepoints"]}
        assert {"suez_canal", "strait_of_hormuz", "panama_canal", "malacca_strait"} <= ids
        # Land + water blockades are both represented, with an optimal solution.
        kinds = {cp.get("kind") for cp in data["chokepoints"]}
        assert {"maritime", "land"} <= kinds
        assert all(cp.get("solution") for cp in data["chokepoints"])


def test_route_simulate_clear() -> None:
    """Unblocked voyage returns status 'clear' and a baseline route."""
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/supply-chain/routes/simulate",
            json={
                "origin": "shanghai",
                "destination": "rotterdam",
                "blocked_chokepoints": [],
                "event_type": "war_conflict",
                "include_news": False,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "clear"
        assert data["baseline"]["total_km"] > 10_000
        assert data["diverted"] is None


def test_route_simulate_diverted() -> None:
    """Blocking the Eurasian land bridge diverts Shanghai→Rotterdam to sea."""
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/supply-chain/routes/simulate",
            json={
                "origin": "shanghai",
                "destination": "rotterdam",
                "blocked_chokepoints": ["eu_asia_rail"],
                "event_type": "war_conflict",
                "include_news": False,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "diverted"
        assert data["diverted"] is not None
        assert data["impact"]["extra_km"] > 0
        assert data["impact"]["extra_days"] > 0
        assert data["recommendation"]


def test_route_simulate_sea_blockade_diverts() -> None:
    """Blocking Suez + Red Sea still diverts a route that uses them."""
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/supply-chain/routes/simulate",
            json={
                "origin": "singapore",
                "destination": "rotterdam",
                "blocked_chokepoints": ["suez_canal", "red_sea", "bab_el_mandeb", "gulf_of_aden"],
                "event_type": "war_conflict",
                "include_news": False,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "diverted"
        assert data["diverted"] is not None
        assert data["impact"]["extra_km"] > 0


def test_route_simulate_invalid_port() -> None:
    """Unknown ports return 422."""
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/supply-chain/routes/simulate",
            json={"origin": "atlantis", "destination": "rotterdam", "blocked_chokepoints": [], "include_news": False},
        )
        assert r.status_code == 422


def test_route_event_types() -> None:
    """GET /routes/event-types lists disruption presets."""
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    with TestClient(app) as client:
        r = client.get("/api/v1/supply-chain/routes/event-types")
        assert r.status_code == 200
        events = r.json()["events"]
        assert any(e["id"] == "war_conflict" for e in events)
