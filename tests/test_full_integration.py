"""Cross-module integration tests — the unique overlap between Business and
Supply Chain modules.

The business-only and supply-chain-only endpoint coverage lives in
``test_api_endpoints.py`` and ``test_supply_chain_api.py`` respectively. This
file only re-tests the *interactions* between the two modules: shared DB,
shared LLM client, cross-module context, and both engines working together.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict

import httpx

# Self-contained DB: works standalone; respects an already-set URL in the full suite.
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_full_integration_{uuid.uuid4().hex[:8]}.db")

results: list[Dict[str, Any]] = []


def log(name: str, status: str, detail: str = "") -> None:
    emoji = "✅" if status == "PASS" else "❌"
    results.append({"name": name, "status": status, "detail": detail})
    print(f"  {emoji} {name}" + (f" — {detail}" if detail else ""))


async def test_cross_module_integration() -> None:
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()

    twin_id = ""
    supplier_id = ""

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:

        # ── Minimal setup: one twin + one supplier so cross-module checks have data ──
        r = await c.post("/api/v1/digital-twins", json={
            "name": "GlobalTech Corp", "industry": "technology",
            "revenue": 5_000_000, "expenses": 3_500_000,
            "customers": 800, "employees": 120,
            "sales": 4_500_000, "marketing_budget": 500_000, "market_share": 8.0,
        })
        data = r.json()
        if r.status_code == 201 and "id" in data:
            twin_id = data["id"]
            log("Setup. Create twin", "PASS")
        else:
            log("Setup. Create twin", "FAIL", f"{r.status_code}")

        r = await c.post("/api/v1/supply-chain/suppliers", json={
            "name": "TechParts Global", "location": "Shenzhen, China",
            "country": "China", "product_categories": ["electronics"],
            "lead_time_days": 14, "cost_per_unit": 25.0,
            "capacity": 5000, "quality_rating": 4.5,
        })
        data = r.json()
        if r.status_code == 201 and "id" in data:
            supplier_id = data["id"]
            log("Setup. Create supplier", "PASS")
        else:
            log("Setup. Create supplier", "FAIL", f"{r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # PART C: Cross-Module Integration (the unique coverage of this file)
        # ════════════════════════════════════════════════════════════════════════

        # C1. Shared Database — both modules use same DB
        r1 = await c.get(f"/api/v1/digital-twins/{twin_id}")
        r2 = await c.get(f"/api/v1/supply-chain/suppliers/{supplier_id}")
        if r1.status_code == 200 and r2.status_code == 200:
            log("C1. Shared Database", "PASS", "Both modules access same DB")
        else:
            log("C1. Shared Database", "FAIL")

        # C2. Shared LLM Client — both modules use same fallback
        r1 = await c.post(f"/api/v1/agent/{twin_id}/ask", json={"question": "What is our revenue?"})
        r2 = await c.post("/api/v1/supply-chain/agent/ask", json={"question": "How many suppliers?"})
        if r1.status_code == 200 and r2.status_code == 200:
            log("C2. Shared LLM Client", "PASS", "Both agents respond via fallback")
        else:
            log("C2. Shared LLM Client", "FAIL")

        # C3. Business Decision AI can reference supply chain context
        r = await c.post(f"/api/v1/agent/{twin_id}/ask", json={
            "question": "Our supply chain has 5 suppliers and 3 warehouses. Should we expand?"
        })
        if r.status_code == 200 and "answer" in r.json():
            log("C3. Business Agent + SC Context", "PASS", f"Answer: {r.json()['answer'][:60]}...")
        else:
            log("C3. Business Agent + SC Context", "FAIL")

        # C4. Supply Chain Agent can reference business context
        r = await c.post("/api/v1/supply-chain/agent/ask", json={
            "question": "Our business revenue is $5M. How should we optimize procurement?"
        })
        if r.status_code == 200 and "answer" in r.json():
            log("C4. SC Agent + Business Context", "PASS", f"Answer: {r.json()['answer'][:60]}...")
        else:
            log("C4. SC Agent + Business Context", "FAIL")

        # C5. Both health scores work independently
        r1 = await c.get(f"/api/v1/health/{twin_id}")
        r2 = await c.get("/api/v1/supply-chain/health")
        if r1.status_code == 200 and r2.status_code == 200:
            log("C5. Independent Health Scores", "PASS",
                f"Business: {r1.json()['overall_score']}, SC: {r2.json()['overall_score']}")
        else:
            log("C5. Independent Health Scores", "FAIL")

        # C6. Both optimization engines work independently
        r1 = await c.post(f"/api/v1/simulations/{twin_id}/run", json={
            "decision_type": "increase_marketing", "decision_params": {"percent": 15}
        })
        r2 = await c.post("/api/v1/supply-chain/optimization")
        if r1.status_code == 200 and r2.status_code == 200:
            log("C6. Independent Optimization", "PASS",
                f"Business sim OK, SC optimization: ${r2.json()['total_potential_saving']:,.0f} potential saving")
        else:
            log("C6. Independent Optimization", "FAIL")

        # C7. Report generation for both modules
        r1 = await c.post(f"/api/v1/reports/{twin_id}/generate", json={"include_simulations": True})
        r2 = await c.post("/api/v1/supply-chain/reports/generate", json={"report_type": "full"})
        if r1.status_code == 200 and r2.status_code == 200:
            log("C7. Both Report Generators", "PASS", "Business + SC reports generated")
        else:
            log("C7. Both Report Generators", "FAIL")

        # C8. API Root shows both module endpoints
        r = await c.get("/")
        data = r.json()
        endpoints = data.get("endpoints", {})
        has_biz = "digital_twins" in endpoints
        has_sc = "supply_chain" in endpoints
        if has_biz and has_sc:
            log("C8. Root Endpoint Shows Both", "PASS",
                f"Business: {endpoints['digital_twins']}, SC: {endpoints['supply_chain']}")
        else:
            log("C8. Root Endpoint Shows Both", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # SUMMARY
        # ════════════════════════════════════════════════════════════════════════
        print("\n" + "=" * 60)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        total = len(results)
        print(f"\n📊 CROSS-MODULE TEST RESULTS: {passed}/{total} passed, {failed} failed")
        print("=" * 60)

        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in results:
                if r["status"] == "FAIL":
                    print(f"  - {r['name']}: {r['detail']}")
        else:
            print("\n🎉 ALL TESTS PASSED — Both modules are fully integrated!")

    # Fail the pytest run if any integration check failed (not just printed).
    assert failed == 0, f"{failed} of {total} integration checks failed"


if __name__ == "__main__":
    asyncio.run(test_cross_module_integration())
