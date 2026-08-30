"""Tests for the Agentic AI layer — orchestration, briefing and market watch."""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx

# Self-contained DB: works standalone; respects an already-set URL in the full suite.
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_agentic_{uuid.uuid4().hex[:8]}.db")
# A1 seeds through the seed API — enable it explicitly (off by default in prod).
os.environ.setdefault("ENABLE_SEED_API", "true")

results: list[dict] = []


def log(name: str, status: str, detail: str = "") -> None:
    emoji = "✅" if status == "PASS" else "❌"
    results.append({"name": name, "status": status, "detail": detail})
    print(f"  {emoji} {name}" + (f" — {detail}" if detail else ""))


async def test_agentic_ai() -> None:
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:

        # A1. Seed a twin so the agents have data to inspect.
        r = await c.post("/api/v1/system/seed", json={"force": True})
        if r.status_code == 200:
            log("A1. Seed twin", "PASS")
        else:
            log("A1. Seed twin", "FAIL", f"{r.status_code}")

        twins = (await c.get("/api/v1/digital-twins")).json()
        twin_id = twins[0]["id"] if twins else ""

        # A2. Orchestrate — full multi-agent pipeline with reasoning trace.
        r = await c.post(
            f"/api/v1/agentic/{twin_id}/orchestrate",
            json={"question": "Complete business assessment please"},
        )
        data = r.json()
        ok = r.status_code == 200 and data.get("answer") and data.get("recommendation")
        if ok:
            agents = {s["agent"] for s in data["steps"]}
            has_tools = any(s["phase"] == "tool_call" for s in data["steps"])
            all_agents = {"financial", "market", "supply_chain", "strategy"} <= agents
            log("A2. Orchestrate with trace", "PASS" if all_agents and has_tools else "FAIL",
                f"steps={len(data['steps'])}, agents={sorted(agents)}, tools={'yes' if has_tools else 'no'}")
        else:
            log("A2. Orchestrate with trace", "FAIL", f"{r.status_code}")

        # A3. Briefing — one-shot executive report.
        r = await c.post(f"/api/v1/agentic/{twin_id}/briefing")
        data = r.json()
        ok = r.status_code == 200 and data.get("company") and len(data.get("sections", [])) >= 3 and data.get("top_recommendations")
        log("A3. Executive briefing", "PASS" if ok else "FAIL",
            f"sections={len(data.get('sections', []))}, recs={len(data.get('top_recommendations', []))}" if ok else f"{r.status_code}")

        # A4. Market watch — watchlist with news + impact scores.
        r = await c.get("/api/v1/market/watch")
        data = r.json()
        ok = r.status_code == 200 and len(data.get("items", [])) >= 3
        if ok:
            first = data["items"][0]
            valid = first["category"] in ("commodity", "freight", "geopolitical", "index") and 0 <= first["impact_score"] <= 100
            log("A4. Market watch", "PASS" if valid else "FAIL", f"items={len(data['items'])}, mode={data['mode']}")
        else:
            log("A4. Market watch", "FAIL", f"{r.status_code}")

        # A5. Agentic 404 for unknown twin.
        r = await c.post(f"/api/v1/agentic/{uuid.uuid4()}/orchestrate", json={"question": "Full assessment please"})
        log("A5. 404 for unknown twin", "PASS" if r.status_code == 404 else "FAIL", str(r.status_code))

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"\n📊 AGENTIC TEST RESULTS: {passed}/{len(results)} passed, {failed} failed")
    assert failed == 0, f"{failed} of {len(results)} agentic checks failed"


if __name__ == "__main__":
    asyncio.run(test_agentic_ai())
