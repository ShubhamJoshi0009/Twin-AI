"""Tests for the trade-route risk discovery engine + API endpoint."""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx

# Self-contained DB + no NewsAPI key (keeps the news chain deterministic;
# GDELT may still return live headlines when the sandbox has network, so
# assertions never depend on mode being \"curated\").
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_route_risk_{uuid.uuid4().hex[:8]}.db")
os.environ["NEWS_API_KEY"] = ""

results: list[dict] = []


def log(name: str, status: str, detail: str = "") -> None:
    emoji = "✅" if status == "PASS" else "❌"
    results.append({"name": name, "status": status, "detail": detail})
    print(f"  {emoji} {name}" + (f" — {detail}" if detail else ""))


def test_classify_event_types() -> None:
    from business_twin_ai.supply_chain.engines.discovery import _classify_event

    cases = [
        ("Houthi missile attacks target cargo ship in Red Sea", "war_conflict"),
        ("Pirates hijack tanker near Malacca Strait", "piracy"),
        ("Typhoon forces closure of Shanghai container port", "natural_disaster"),
        ("US imposes sanctions on Iranian shipping lines", "sanctions"),
        ("Panama Canal drought cuts daily transits again", "congestion"),
        ("Container ship runs aground in Suez Canal", "grounding"),
        ("Freight rates hold steady this week", "congestion"),
    ]
    for headline, expected in cases:
        assert _classify_event(headline) == expected, headline
    log("R1. Event classification", "PASS")


def test_score_headline_escalates() -> None:
    from business_twin_ai.supply_chain.engines.discovery import _score_headline
    from business_twin_ai.supply_chain.engines.routes import CHOKEPOINTS

    meta = CHOKEPOINTS["suez_canal"]
    calm = _score_headline("Shipping resumes through Suez after recovery", meta, "congestion")
    crisis = _score_headline("Suez Canal shut — emergency suspension of all transits", meta, "war_conflict")
    assert crisis > calm, f"crisis={crisis} should exceed calm={calm}"
    assert 5 <= calm <= 98 and 5 <= crisis <= 98
    log("R2. Escalation scoring", "PASS")


def test_severity_thresholds() -> None:
    from business_twin_ai.supply_chain.engines.discovery import _severity_for

    assert _severity_for(80) == "critical"
    assert _severity_for(60) == "high"
    assert _severity_for(40) == "medium"
    assert _severity_for(15) == "low"
    log("R3. Severity thresholds", "PASS")


async def test_discover_and_endpoint() -> None:
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        # R4. Discovery engine returns ranked scenarios for every chokepoint.
        from business_twin_ai.supply_chain.engines.discovery import discover_route_scenarios

        result = await discover_route_scenarios(limit=10, news_limit=2)
        scenarios = result["scenarios"]
        ok = len(scenarios) >= 1 and result["mode"] in ("live", "curated")
        scores = [s["risk_score"] for s in scenarios]
        ranked = scores == sorted(scores, reverse=True)
        first = scenarios[0]
        fields = ("scenario_id", "chokepoint_id", "chokepoint_name", "event_type",
                  "severity", "risk_score", "headline", "source", "summary")
        complete = all(f in first for f in fields)
        log("R4. Discovery engine", "PASS" if ok and ranked and complete else "FAIL",
            f"mode={result['mode']}, scenarios={len(scenarios)}, ranked={ranked}")

        # R5. API endpoint returns a valid payload.
        r = await c.get("/api/v1/supply-chain/routes/risk-scenarios", params={"limit": 4})
        data = r.json()
        ok = r.status_code == 200 and "scenarios" in data and "mode" in data
        ok = ok and len(data["scenarios"]) <= 4
        log("R5. GET /routes/risk-scenarios", "PASS" if ok else "FAIL", f"status={r.status_code}, count={len(data.get('scenarios', []))}")

        # R6. Limit validation.
        bad0 = await c.get("/api/v1/supply-chain/routes/risk-scenarios", params={"limit": 0})
        bad99 = await c.get("/api/v1/supply-chain/routes/risk-scenarios", params={"limit": 99})
        ok = bad0.status_code == 422 and bad99.status_code == 422
        log("R6. Limit validation", "PASS" if ok else "FAIL", f"limit=0 → {bad0.status_code}, limit=99 → {bad99.status_code}")

        # R7. Route simulate still works (regression — discovery touched the router).
        r = await c.post("/api/v1/supply-chain/routes/simulate", json={
            "origin": "shanghai", "destination": "rotterdam",
            "blocked_chokepoints": ["suez_canal"], "event_type": "war_conflict",
            "cargo_value": 1_000_000, "include_news": False,
        })
        data = r.json()
        ok = r.status_code == 200 and data.get("status") in ("diverted", "no_alternative", "clear")
        log("R7. Route simulate regression", "PASS" if ok else "FAIL", f"status={r.status_code}")


def test_route_risk_ai() -> None:
    asyncio.run(test_discover_and_endpoint())


if __name__ == "__main__":
    asyncio.run(test_discover_and_endpoint())
    failed = [r for r in results if r["status"] == "FAIL"]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for r in failed:
        print(f"  ❌ {r['name']}: {r['detail']}")
    raise SystemExit(1 if failed else 0)
