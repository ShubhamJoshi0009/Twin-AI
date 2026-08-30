"""Tests for real-time route-weather monitoring (risk engine + API).

Runs with ``WEATHER_FORCE_SIMULATED=true`` so the suite is fully
deterministic and offline-safe: every port/route uses the simulated provider,
and assertions never depend on live Open-Meteo availability.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_route_weather_{uuid.uuid4().hex[:8]}.db")
# Force the deterministic simulated provider for the whole process.
os.environ["WEATHER_FORCE_SIMULATED"] = "true"

results: list[dict] = []


def log(name: str, status: str, detail: str = "") -> None:
    emoji = "✅" if status == "PASS" else "❌"
    results.append({"name": name, "status": status, "detail": detail})
    print(f"  {emoji} {name}" + (f" — {detail}" if detail else ""))


# ── Risk engine unit tests ───────────────────────────────────────────────────

def test_weather_label_mapping() -> None:
    from business_twin_ai.services.weather.open_meteo import weather_label

    assert weather_label(0) == ("Clear sky", "☀️")
    assert weather_label(3)[0] == "Overcast"
    assert weather_label(63)[0] == "Rain"
    assert weather_label(95)[0] == "Thunderstorm"
    # Unknown codes degrade to a sensible family label, never crash.
    label, icon = weather_label(999)
    assert label and icon
    log("W1. WMO code → label", "PASS")


def test_risk_level_thresholds() -> None:
    from business_twin_ai.services.weather.risk import risk_level

    assert risk_level(0) == "GREEN"
    assert risk_level(24) == "GREEN"
    assert risk_level(26) == "YELLOW"
    assert risk_level(49) == "YELLOW"
    assert risk_level(52) == "ORANGE"
    assert risk_level(74) == "ORANGE"
    assert risk_level(80) == "RED"
    log("W2. Risk level thresholds", "PASS")


def test_hazard_scoring_monotonic() -> None:
    from business_twin_ai.services.weather.risk import conditions_risk

    calm = conditions_risk({"temperature_c": 25, "wind_speed_kmh": 10,
                            "wind_gusts_kmh": 14, "precipitation_mm": 0, "weather_code": 0})
    windy = conditions_risk({"temperature_c": 25, "wind_speed_kmh": 65,
                             "wind_gusts_kmh": 90, "precipitation_mm": 0, "weather_code": 0})
    storm = conditions_risk({"temperature_c": 25, "wind_speed_kmh": 65,
                             "wind_gusts_kmh": 90, "precipitation_mm": 20, "weather_code": 95})

    assert calm["risk_score"] < windy["risk_score"] < storm["risk_score"]
    assert calm["level"] == "GREEN"
    assert storm["level"] in ("ORANGE", "RED")
    # Hazards are explainable (named contributions).
    assert set(calm["hazards"]) == {
        "wind", "precipitation", "weather_code", "temperature"
    }
    log("W3. Hazard scoring monotonic", "PASS",
        f"calm={calm['risk_score']} windy={windy['risk_score']} storm={storm['risk_score']}")


def test_route_aggregation_worst_dominates() -> None:
    from business_twin_ai.services.weather.risk import route_weather_risk

    points = [
        {"label": "A", "lat": 1, "lng": 2, "conditions": {
            "temperature_c": 25, "wind_speed_kmh": 10,
            "wind_gusts_kmh": 14, "precipitation_mm": 0, "weather_code": 0,
        }},
        {"label": "B", "lat": 3, "lng": 4, "conditions": {
            "temperature_c": 25, "wind_speed_kmh": 95,
            "wind_gusts_kmh": 120, "precipitation_mm": 40, "weather_code": 99,
        }},
    ]
    result = route_weather_risk(points)
    assert result["worst"]["label"] == "B"
    assert len(result["alerts"]) == 1  # B is RED/ORANGE
    assert result["alerts"][0]["location"] == "B"
    # Overall nudged above the calm point's score because of the severe one.
    assert result["risk_score"] > 30
    assert result["level"] in ("ORANGE", "RED")
    log("W4. Route aggregation", "PASS",
        f"overall={result['risk_score']} level={result['level']} alerts={len(result['alerts'])}")


def test_worst_level() -> None:
    from business_twin_ai.services.weather.risk import worst_level

    assert worst_level("GREEN", "RED", "YELLOW") == "RED"
    assert worst_level("YELLOW", "ORANGE") == "ORANGE"
    assert worst_level(None, None) == "GREEN"
    log("W5. worst_level", "PASS")


# ── Simulated fallback unit tests ────────────────────────────────────────────

def test_simulated_conditions_deterministic_and_plausible() -> None:
    from business_twin_ai.services.weather.open_meteo import _simulated_conditions

    a1 = _simulated_conditions(28.61, 77.23)
    a2 = _simulated_conditions(28.61, 77.23)
    b = _simulated_conditions(-33.92, 18.42)

    assert a1 == a2  # deterministic within a time bucket
    assert a1["source"] == "simulated"
    for key in ("weather_code", "temperature_c", "wind_speed_kmh"):
        assert key in a1
    assert -60 <= a1["temperature_c"] <= 60
    assert 0 <= a1["wind_speed_kmh"] <= 120
    assert 0 <= a1["precipitation_mm"] <= 20
    # Coordinates far apart always differ in at least one condition field.
    same_cond = a1["temperature_c"] == b["temperature_c"]
    same_cond = same_cond and a1["weather_code"] == b["weather_code"]
    same_cond = same_cond and a1["wind_speed_kmh"] == b["wind_speed_kmh"]
    assert not same_cond
    log("W6. Simulated fallback", "PASS")


def test_fetch_weather_returns_conditions_offline() -> None:
    async def _run() -> None:
        from business_twin_ai.services.weather.open_meteo import fetch_weather

        conditions = await fetch_weather(1.35, 103.82)  # Singapore
        assert conditions["source"] == "simulated"
        assert conditions["weather_label"]
        assert isinstance(conditions["temperature_c"], float)

    asyncio.run(_run())
    log("W7. fetch_weather offline fallback", "PASS")


def test_parse_current_handles_scalar_and_array_payloads() -> None:
    from business_twin_ai.services.weather.open_meteo import _parse_current

    # Single-location payload: scalar current values.
    scalar = {
        "current": {
            "temperature_2m": 26.2, "weather_code": 1,
            "wind_speed_10m": 5.9, "time": "2026-08-07T19:45",
        }
    }
    c1 = _parse_current(scalar, 1.35, 103.82)
    assert c1["source"] == "live" and c1["temperature_c"] == 26.2
    assert c1["weather_label"] == "Mainly clear"

    # Array-valued payload (indexed by location in request order).
    array = {
        "current": {
            "temperature_2m": [26.2, 20.6, 34.9],
            "weather_code": [1, 0, 0],
            "wind_speed_10m": [5.9, 8.3, 12.0],
        }
    }
    c2 = _parse_current(array, 51.92, 4.48, index=1)
    assert c2["temperature_c"] == 20.6
    c3 = _parse_current(array, 25.20, 55.27, index=2)
    assert c3["temperature_c"] == 34.9 and c3["source"] == "live"
    log("W13. Payload formats (scalar + array)", "PASS")


def test_fetch_live_batch_handles_list_of_payloads() -> None:
    """Open-Meteo returns a JSON *list* of per-location payloads for
    multi-location requests — the batch parser must map them back to the
    requested coordinates in order (regression for the all-simulated bug).
    """
    import business_twin_ai.services.weather.open_meteo as om

    class _FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self):
            return [
                {"current": {"temperature_2m": 26.2, "weather_code": 1,
                             "time": "2026-08-07T19:45"}},
                {"current": {"temperature_2m": 20.6, "weather_code": 0,
                             "time": "2026-08-07T19:45"}},
            ]

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return False

        async def get(self, url, params):
            return _FakeResponse()

    async def _run() -> None:
        om._cache.clear()
        original = om.httpx.AsyncClient
        om.httpx.AsyncClient = _FakeClient  # type: ignore[assignment]
        try:
            out = await om._fetch_live_batch([(1.35, 103.82), (51.92, 4.48)])
        finally:
            om.httpx.AsyncClient = original
        assert out[(1.35, 103.82)]["source"] == "live"
        assert out[(1.35, 103.82)]["temperature_c"] == 26.2
        assert out[(51.92, 4.48)]["temperature_c"] == 20.6
        assert len(out) == 2

    asyncio.run(_run())
    log("W14. Live batch list-format parse", "PASS")


def test_fetch_weather_batch_keys_by_rounded_coord() -> None:
    async def _run() -> None:
        from business_twin_ai.services.weather.open_meteo import fetch_weather_batch

        batch = await fetch_weather_batch(
            [(31.23, 121.47), (51.92, 4.48), (51.92, 4.48)]
        )
        assert len(batch) == 2  # duplicate rounded coords dedupe
        assert all(c["source"] == "simulated" for c in batch.values())

    asyncio.run(_run())
    log("W8. Batch fetch dedupe + fallback", "PASS")


# ── API integration ──────────────────────────────────────────────────────────

async def test_weather_api() -> None:
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # W9. Global overlay: all ports + lanes + summary.
        r = await c.get("/api/v1/supply-chain/routes/weather")
        data = r.json()
        ok = r.status_code == 200
        ok = ok and data["mode"] in ("live", "simulated")
        ok = ok and len(data["ports"]) >= 24 and len(data["lanes"]) >= 30
        ok = ok and "worst_level" in data["summary"]
        ok = ok and data["summary"]["ports"] == len(data["ports"])
        port0 = data["ports"][0]
        ok = ok and all(
            k in port0["conditions"]
            for k in ("temperature_c", "wind_speed_kmh", "weather_icon", "source")
        )
        log("W9. GET /routes/weather overlay", "PASS" if ok else "FAIL",
            f"status={r.status_code}, ports={len(data.get('ports', []))}, "
            f"lanes={len(data.get('lanes', []))}, mode={data.get('mode')}")

        # W10. Per-route weather detail.
        r = await c.get(
            "/api/v1/supply-chain/routes/weather/route",
            params={"origin": "shanghai", "destination": "rotterdam"},
        )
        data = r.json()
        ok = r.status_code == 200
        ok = ok and data["origin"] == "shanghai"
        ok = ok and data["destination"] == "rotterdam"
        ok = ok and len(data["points"]) >= 2
        ok = ok and data["overall_level"] in ("GREEN", "YELLOW", "ORANGE", "RED")
        ok = ok and data["recommendation"]
        ok = ok and 0 <= data["overall_risk_score"] <= 100
        log("W10. GET /routes/weather/route detail", "PASS" if ok else "FAIL",
            f"status={r.status_code}, points={len(data.get('points', []))}, "
            f"overall={data.get('overall_level')}")

        # W11. Validation: unknown / same ports → 422.
        bad1 = await c.get(
            "/api/v1/supply-chain/routes/weather/route",
            params={"origin": "atlantis", "destination": "rotterdam"},
        )
        bad2 = await c.get(
            "/api/v1/supply-chain/routes/weather/route",
            params={"origin": "rotterdam", "destination": "rotterdam"},
        )
        bad3 = await c.get(
            "/api/v1/supply-chain/routes/weather/route",
            params={"origin": "shanghai"},
        )
        ok = (
            bad1.status_code == 422 and bad2.status_code == 422
            and bad3.status_code == 422
        )
        log("W11. Route weather validation", "PASS" if ok else "FAIL",
            f"unknown→{bad1.status_code}, same→{bad2.status_code}, "
            f"missing→{bad3.status_code}")

        # W12. Existing route simulator still works (regression).
        r = await c.post("/api/v1/supply-chain/routes/simulate", json={
            "origin": "singapore", "destination": "rotterdam",
            "blocked_chokepoints": ["suez_canal"], "event_type": "war_conflict",
            "cargo_value": 1_000_000, "include_news": False,
        })
        ok = r.status_code == 200 and r.json().get("status") in (
            "diverted", "no_alternative", "clear"
        )
        log("W12. Route simulate regression", "PASS" if ok else "FAIL", f"status={r.status_code}")


def test_weather_api_sync() -> None:
    asyncio.run(test_weather_api())


if __name__ == "__main__":
    asyncio.run(test_weather_api())
    failed = [r for r in results if r["status"] == "FAIL"]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for r in failed:
        print(f"  ❌ {r['name']}: {r['detail']}")
    raise SystemExit(1 if failed else 0)
