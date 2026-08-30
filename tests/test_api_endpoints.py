"""Comprehensive API endpoint integration tests.

Tests all 15 API endpoints by starting a FastAPI test server
and making requests using httpx AsyncClient.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any, Dict

import httpx

# ── Test Configuration ───────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
TEST_DB = f"test_integration_{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

# Results tracking
results: list[Dict[str, Any]] = []


def log_test(name: str, status: str, detail: str = "") -> None:
    """Log a test result."""
    emoji = "✅" if status == "PASS" else "❌"
    results.append({"name": name, "status": status, "detail": detail})
    print(f"  {emoji} {name}" + (f" — {detail}" if detail else ""))


async def test_all_endpoints() -> None:
    """Test all API endpoints end-to-end."""
    # Import and create app
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()

    twin_id: str = ""
    sim_id: str = ""

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:

        # ════════════════════════════════════════════════════════════════════════
        # 1. Health Check
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 1. System Health Check ═══")
        r = await client.get("/health")
        if r.status_code == 200 and r.json().get("status") == "healthy":
            log_test("GET /health", "PASS", "Server is healthy")
        else:
            log_test("GET /health", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 2. Root Endpoint
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 2. Root Endpoint ═══")
        r = await client.get("/")
        data = r.json()
        if r.status_code == 200 and "endpoints" in data:
            log_test("GET /", "PASS", f"API base: {data['api_base']}")
        else:
            log_test("GET /", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 3. Create Digital Twin
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 3. Create Digital Twin ═══")
        twin_data = {
            "name": "Acme Corp",
            "industry": "retail",
            "revenue": 2_000_000,
            "expenses": 1_500_000,
            "customers": 500,
            "employees": 80,
            "sales": 1_800_000,
            "marketing_budget": 200_000,
            "market_share": 5.0,
        }
        r = await client.post("/api/v1/digital-twins", json=twin_data)
        data = r.json()
        if r.status_code == 201 and "id" in data:
            twin_id = data["id"]
            log_test("POST /api/v1/digital-twins", "PASS", f"Created twin: {data['name']} (ID: {twin_id[:8]}...)")
            log_test("  - Profit auto-calc", "PASS" if data["profit"] == 500_000 else "FAIL",
                     f"Profit: {data['profit']}")
            log_test("  - KPIs computed", "PASS" if data.get("kpis") else "FAIL")
        else:
            log_test("POST /api/v1/digital-twins", "FAIL", f"Status: {r.status_code}, Body: {data}")

        # ════════════════════════════════════════════════════════════════════════
        # 4. List Digital Twins
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 4. List Digital Twins ═══")
        r = await client.get("/api/v1/digital-twins")
        data = r.json()
        if r.status_code == 200 and isinstance(data, list) and len(data) >= 1:
            log_test("GET /api/v1/digital-twins", "PASS", f"Found {len(data)} twin(s)")
        else:
            log_test("GET /api/v1/digital-twins", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 5. Get Digital Twin by ID
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 5. Get Digital Twin ═══")
        r = await client.get(f"/api/v1/digital-twins/{twin_id}")
        data = r.json()
        if r.status_code == 200 and data.get("name") == "Acme Corp":
            log_test("GET /api/v1/digital-twins/{id}", "PASS", f"Name: {data['name']}")
        else:
            log_test("GET /api/v1/digital-twins/{id}", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 6. Update Digital Twin
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 6. Update Digital Twin ═══")
        update_data = {
            "name": "Acme Corp",
            "industry": "retail",
            "revenue": 2_500_000,
            "expenses": 1_600_000,
            "customers": 600,
            "employees": 90,
            "sales": 2_200_000,
            "marketing_budget": 250_000,
            "market_share": 6.5,
        }
        r = await client.put(f"/api/v1/digital-twins/{twin_id}", json=update_data)
        data = r.json()
        if r.status_code == 200 and data["revenue"] == 2_500_000:
            log_test("PUT /api/v1/digital-twins/{id}", "PASS", f"Revenue updated to {data['revenue']}")
        else:
            log_test("PUT /api/v1/digital-twins/{id}", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 7. List Decision Types
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 7. List Decision Types ═══")
        r = await client.get("/api/v1/simulations/decision-types")
        data = r.json()
        types = data.get("decision_types", [])
        if r.status_code == 200 and len(types) == 13:
            log_test("GET /api/v1/simulations/decision-types", "PASS", f"Found {len(types)} decision types")
        else:
            log_test("GET /api/v1/simulations/decision-types", "FAIL",
                     f"Status: {r.status_code}, Count: {len(types)}")

        # ════════════════════════════════════════════════════════════════════════
        # 8. Run Simulation
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 8. Run Simulation ═══")
        sim_request = {
            "decision_type": "increase_marketing",
            "decision_params": {"percent": 20},
        }
        r = await client.post(f"/api/v1/simulations/{twin_id}/run", json=sim_request)
        data = r.json()
        if r.status_code == 200 and "id" in data:
            sim_id = data["id"]
            log_test("POST /api/v1/simulations/{id}/run", "PASS", f"Simulation: {data['decision_type']}")
            log_test("  - Predictions", "PASS" if data.get("predictions") else "FAIL")
            log_test("  - Scenarios", "PASS" if data.get("scenarios") else "FAIL",
                     f"Count: {len(data.get('scenarios', []))}")
            log_test("  - Confidence", "PASS" if data.get("confidence") else "FAIL",
                     f"Score: {data.get('confidence', {}).get('score', 'N/A')}")
            log_test("  - Recommendation", "PASS" if data.get("recommendation") else "FAIL")
            log_test("  - Explanation", "PASS" if data.get("explanation") else "FAIL")
        else:
            log_test("POST /api/v1/simulations/{id}/run", "FAIL", f"Status: {r.status_code}, Body: {data}")

        # ════════════════════════════════════════════════════════════════════════
        # 9. Get Health Score
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 9. Get Health Score ═══")
        r = await client.get(f"/api/v1/health/{twin_id}")
        data = r.json()
        if r.status_code == 200 and "overall_score" in data:
            log_test("GET /api/v1/health/{id}", "PASS",
                     f"Score: {data['overall_score']}, Trend: {data['trend']}")
            log_test("  - Category scores", "PASS" if data.get("category_scores") else "FAIL",
                     f"Categories: {len(data.get('category_scores', {}))}")
            log_test("  - Suggestions", "PASS" if data.get("suggestions") else "FAIL",
                     f"Count: {len(data.get('suggestions', []))}")
        else:
            log_test("GET /api/v1/health/{id}", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 10. Generate Strategies
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 10. Generate Strategies ═══")
        r = await client.post(f"/api/v1/strategies/{twin_id}/generate")
        data = r.json()
        if r.status_code == 200 and "strategies" in data:
            strats = data["strategies"]
            log_test("POST /api/v1/strategies/{id}/generate", "PASS",
                     f"Generated {len(strats)} strategies")
            for s in strats[:3]:
                log_test(f"  - {s['strategy_type']}", "PASS", f"{s['title']} (Priority: {s['priority']})")
        else:
            log_test("POST /api/v1/strategies/{id}/generate", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 11. Ask Business Agent
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 11. Ask Business Agent ═══")
        r = await client.post(
            f"/api/v1/agent/{twin_id}/ask",
            json={"question": "Should we increase prices?"},
        )
        data = r.json()
        if r.status_code == 200 and "answer" in data:
            answer_preview = data["answer"][:100] + "..." if len(data["answer"]) > 100 else data["answer"]
            log_test("POST /api/v1/agent/{id}/ask", "PASS", f"Answer: {answer_preview}")
            log_test("  - Confidence", "PASS" if "confidence" in data else "FAIL",
                     f"Score: {data.get('confidence', 'N/A')}")
        else:
            log_test("POST /api/v1/agent/{id}/ask", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 12. Generate Insights
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 12. Generate Insights ═══")
        r = await client.post(f"/api/v1/insights/{twin_id}/generate")
        data = r.json()
        if r.status_code == 200 and isinstance(data, list):
            log_test("POST /api/v1/insights/{id}/generate", "PASS", f"Generated {len(data)} insights")
            for ins in data[:3]:
                log_test(f"  - [{ins['severity']}]", "PASS", f"{ins['title']}")
        else:
            log_test("POST /api/v1/insights/{id}/generate", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 13. Generate Report
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 13. Generate Report ═══")
        r = await client.post(
            f"/api/v1/reports/{twin_id}/generate",
            json={"include_simulations": True, "include_insights": True, "include_strategies": True},
        )
        data = r.json()
        if r.status_code == 200 and "report_id" in data:
            log_test("POST /api/v1/reports/{id}/generate", "PASS",
                     f"Report: {data['report_id'][:8]}..., Pages: {data['pages']}")
        else:
            log_test("POST /api/v1/reports/{id}/generate", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 14. Get Timeline
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 14. Get Timeline ═══")
        r = await client.get(f"/api/v1/timeline/{twin_id}")
        data = r.json()
        if r.status_code == 200 and isinstance(data, list):
            log_test("GET /api/v1/timeline/{id}", "PASS", f"Timeline entries: {len(data)}")
        else:
            log_test("GET /api/v1/timeline/{id}", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # 15. Compare Scenarios (What-If)
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 15. Compare Scenarios (What-If) ═══")
        compare_request = {
            "scenarios": [
                {"name": "Raise Prices 10%", "decision_type": "increase_price", "decision_params": {"percent": 10}},
                {"name": "More Marketing 20%", "decision_type": "increase_marketing", "decision_params": {"percent": 20}},
            ]
        }
        r = await client.post(f"/api/v1/simulations/{twin_id}/compare", json=compare_request)
        data = r.json()
        if r.status_code == 200 and "comparisons" in data:
            comps = data["comparisons"]
            log_test("POST /api/v1/simulations/{id}/compare", "PASS",
                     f"Compared {len(comps)} scenarios, Winner: {data.get('winner', 'N/A')}")
            for c in comps:
                log_test(f"  - {c['name']}", "PASS",
                         f"Revenue: ${c['revenue']:,.0f}, Profit: ${c['profit']:,.0f}, Risk: {c['risk']:.0f}%")
        else:
            log_test("POST /api/v1/simulations/{id}/compare", "FAIL",
                     f"Status: {r.status_code}, Body: {data}")

        # ════════════════════════════════════════════════════════════════════════
        # 16. Replay Simulation from Timeline
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 16. Replay Simulation ═══")
        if sim_id:
            r = await client.get(f"/api/v1/timeline/{twin_id}/{sim_id}")
            data = r.json()
            if r.status_code == 200 and data.get("id") == sim_id:
                log_test("GET /api/v1/timeline/{id}/{sim_id}", "PASS",
                         f"Replayed: {data['decision_type']}")
            else:
                log_test("GET /api/v1/timeline/{id}/{sim_id}", "FAIL",
                         f"Status: {r.status_code}")
        else:
            log_test("GET /api/v1/timeline/{id}/{sim_id}", "SKIP", "No simulation ID available")

        # ════════════════════════════════════════════════════════════════════════
        # 17. Get Existing Insights
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 17. Get Existing Insights ═══")
        r = await client.get(f"/api/v1/insights/{twin_id}")
        data = r.json()
        if r.status_code == 200 and isinstance(data, list) and len(data) > 0:
            log_test("GET /api/v1/insights/{id}", "PASS", f"Retrieved {len(data)} insights")
        else:
            log_test("GET /api/v1/insights/{id}", "FAIL", f"Status: {r.status_code}, Count: {len(data) if isinstance(data, list) else 'N/A'}")

        # ════════════════════════════════════════════════════════════════════════
        # 18. Error Handling - Invalid Twin ID
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 18. Error Handling ═══")
        r = await client.get(f"/api/v1/digital-twins/{uuid.uuid4()}")
        if r.status_code == 404:
            log_test("Error: Invalid twin ID returns 404", "PASS")
        else:
            log_test("Error: Invalid twin ID returns 404", "FAIL", f"Status: {r.status_code}")

        # Invalid decision type
        r = await client.post(f"/api/v1/simulations/{twin_id}/run", json={
            "decision_type": "invalid_decision",
            "decision_params": {},
        })
        if r.status_code == 400:
            log_test("Error: Invalid decision type returns 400", "PASS")
        else:
            log_test("Error: Invalid decision type returns 400", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # Summary
        # ════════════════════════════════════════════════════════════════════════
        print("\n" + "=" * 60)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        skipped = sum(1 for r in results if r["status"] == "SKIP")
        total = len(results)
        print(f"\n📊 TEST RESULTS: {passed}/{total} passed, {failed} failed, {skipped} skipped")
        print("=" * 60)

        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in results:
                if r["status"] == "FAIL":
                    print(f"  - {r['name']}: {r['detail']}")


if __name__ == "__main__":
    asyncio.run(test_all_endpoints())
