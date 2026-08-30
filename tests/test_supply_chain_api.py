"""Comprehensive API endpoint tests for the Supply Chain AI module."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict

import httpx

BASE_URL = "http://test"
results: list[Dict[str, Any]] = []


def log_test(name: str, status: str, detail: str = "") -> None:
    emoji = "✅" if status == "PASS" else "❌"
    results.append({"name": name, "status": status, "detail": detail})
    print(f"  {emoji} {name}" + (f" — {detail}" if detail else ""))


async def test_all_endpoints() -> None:
    from business_twin_ai.app import app
    from business_twin_ai.database import init_db

    await init_db()

    supplier_id = ""
    warehouse_id = ""
    inventory_id = ""
    shipment_id = ""

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL) as c:

        # ════════════════════════════════════════════════════════════════════════
        # 1. Supplier Management
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 1. Supplier Management ═══")

        r = await c.post("/api/v1/supply-chain/suppliers", json={
            "name": "Test Supplier",
            "location": "New York, USA",
            "country": "USA",
            "product_categories": ["electronics"],
            "lead_time_days": 5,
            "cost_per_unit": 30.0,
            "capacity": 2000,
            "quality_rating": 4.5,
        })
        data = r.json()
        if r.status_code == 201 and "id" in data:
            supplier_id = data["id"]
            log_test("POST /suppliers", "PASS", f"Created: {data['name']}")
        else:
            log_test("POST /suppliers", "FAIL", f"Status: {r.status_code}")

        r = await c.get("/api/v1/supply-chain/suppliers")
        if r.status_code == 200 and len(r.json()) >= 1:
            log_test("GET /suppliers", "PASS", f"Found {len(r.json())} suppliers")
        else:
            log_test("GET /suppliers", "FAIL")

        r = await c.get(f"/api/v1/supply-chain/suppliers/{supplier_id}")
        if r.status_code == 200:
            log_test("GET /suppliers/{id}", "PASS")
        else:
            log_test("GET /suppliers/{id}", "FAIL")

        r = await c.put(f"/api/v1/supply-chain/suppliers/{supplier_id}", json={"quality_rating": 4.8})
        if r.status_code == 200 and r.json()["quality_rating"] == 4.8:
            log_test("PUT /suppliers/{id}", "PASS")
        else:
            log_test("PUT /suppliers/{id}", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 2. Warehouse Management
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 2. Warehouse Management ═══")

        r = await c.post("/api/v1/supply-chain/warehouses", json={
            "name": "Test Warehouse",
            "location": "Boston, MA",
            "capacity": 10000,
            "storage_cost_per_unit": 0.50,
        })
        data = r.json()
        if r.status_code == 201 and "id" in data:
            warehouse_id = data["id"]
            log_test("POST /warehouses", "PASS", f"Created: {data['name']}")
        else:
            log_test("POST /warehouses", "FAIL", f"Status: {r.status_code}")

        r = await c.get("/api/v1/supply-chain/warehouses")
        if r.status_code == 200:
            log_test("GET /warehouses", "PASS", f"Found {len(r.json())} warehouses")
        else:
            log_test("GET /warehouses", "FAIL")

        r = await c.get(f"/api/v1/supply-chain/warehouses/{warehouse_id}")
        if r.status_code == 200:
            log_test("GET /warehouses/{id}", "PASS")
        else:
            log_test("GET /warehouses/{id}", "FAIL")

        r = await c.get(f"/api/v1/supply-chain/warehouses/{warehouse_id}/utilization")
        if r.status_code == 200 and "current_utilization" in r.json():
            log_test("GET /warehouses/{id}/utilization", "PASS")
        else:
            log_test("GET /warehouses/{id}/utilization", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 3. Inventory Management
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 3. Inventory Management ═══")

        r = await c.post("/api/v1/supply-chain/inventory", json={
            "warehouse_id": warehouse_id,
            "product_name": "Test Product",
            "product_sku": "TP-001",
            "category": "electronics",
            "current_stock": 50,
            "reorder_level": 100,
            "safety_stock": 50,
            "max_stock": 2000,
            "unit_cost": 25.0,
        })
        data = r.json()
        if r.status_code == 201 and "id" in data:
            inventory_id = data["id"]
            log_test("POST /inventory", "PASS", f"Created: {data['product_name']}")
        else:
            log_test("POST /inventory", "FAIL", f"Status: {r.status_code}, Body: {data}")

        r = await c.get("/api/v1/supply-chain/inventory")
        if r.status_code == 200:
            log_test("GET /inventory", "PASS", f"Found {len(r.json())} items")
        else:
            log_test("GET /inventory", "FAIL")

        r = await c.get("/api/v1/supply-chain/inventory/anomalies")
        if r.status_code == 200 and "anomalies" in r.json():
            log_test("GET /inventory/anomalies", "PASS", f"Found {r.json()['count']} anomalies")
        else:
            log_test("GET /inventory/anomalies", "FAIL")

        r = await c.post("/api/v1/supply-chain/inventory/optimize")
        if r.status_code == 200 and "optimizations" in r.json():
            log_test("POST /inventory/optimize", "PASS", f"Score: {r.json()['optimization_score']}")
        else:
            log_test("POST /inventory/optimize", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 4. Shipment Management
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 4. Shipment Management ═══")

        r = await c.post("/api/v1/supply-chain/shipments", json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "shipment_number": "SHP-TEST-001",
            "product_name": "Test Product",
            "quantity": 100,
            "origin": "New York, USA",
            "destination": "Boston, MA",
            "distance_km": 300,
            "fuel_cost": 150.0,
            "transport_cost": 500.0,
        })
        data = r.json()
        if r.status_code == 201 and "id" in data:
            shipment_id = data["id"]
            log_test("POST /shipments", "PASS", f"Created: {data['shipment_number']}")
        else:
            log_test("POST /shipments", "FAIL", f"Status: {r.status_code}")

        r = await c.get("/api/v1/supply-chain/shipments")
        if r.status_code == 200:
            log_test("GET /shipments", "PASS", f"Found {len(r.json())} shipments")
        else:
            log_test("GET /shipments", "FAIL")

        r = await c.get("/api/v1/supply-chain/shipments/delayed")
        if r.status_code == 200:
            log_test("GET /shipments/delayed", "PASS", f"Found {len(r.json())} delayed")
        else:
            log_test("GET /shipments/delayed", "FAIL")

        r = await c.post("/api/v1/supply-chain/shipments/optimize-routes")
        if r.status_code == 200 and "routes" in r.json():
            log_test("POST /shipments/optimize-routes", "PASS", f"Routes: {len(r.json()['routes'])}")
        else:
            log_test("POST /shipments/optimize-routes", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 5. Risk Detection & Prediction
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 5. Risk Detection & Prediction ═══")

        r = await c.post("/api/v1/supply-chain/risks/detect")
        if r.status_code == 200:
            log_test("POST /risks/detect", "PASS", f"Detected {len(r.json())} risks")
        else:
            log_test("POST /risks/detect", "FAIL")

        r = await c.get("/api/v1/supply-chain/risks")
        if r.status_code == 200:
            log_test("GET /risks", "PASS", f"Found {len(r.json())} active risks")
        else:
            log_test("GET /risks", "FAIL")

        r = await c.post("/api/v1/supply-chain/risks/predict")
        if r.status_code == 200 and "predictions" in r.json():
            log_test("POST /risks/predict", "PASS", f"Predictions: {len(r.json()['predictions'])}")
        else:
            log_test("POST /risks/predict", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 6. Alerts
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 6. Alerts ═══")

        r = await c.post("/api/v1/supply-chain/alerts/generate")
        if r.status_code == 200:
            log_test("POST /alerts/generate", "PASS", f"Generated {len(r.json())} alerts")
        else:
            log_test("POST /alerts/generate", "FAIL")

        r = await c.get("/api/v1/supply-chain/alerts")
        if r.status_code == 200:
            log_test("GET /alerts", "PASS", f"Found {len(r.json())} active alerts")
        else:
            log_test("GET /alerts", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 7. Supply Chain Agent
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 7. Supply Chain Agent ═══")

        r = await c.post("/api/v1/supply-chain/agent/ask", json={"question": "Which supplier is most risky?"})
        if r.status_code == 200 and "answer" in r.json():
            log_test("POST /agent/ask", "PASS", f"Answer: {r.json()['answer'][:80]}...")
        else:
            log_test("POST /agent/ask", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 8. Health Score
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 8. Supply Chain Health ═══")

        r = await c.get("/api/v1/supply-chain/health")
        if r.status_code == 200 and "overall_score" in r.json():
            log_test("GET /health", "PASS", f"Score: {r.json()['overall_score']}")
        else:
            log_test("GET /health", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 9. Optimization
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 9. Optimization ═══")

        r = await c.post("/api/v1/supply-chain/optimization")
        if r.status_code == 200 and "recommendations" in r.json():
            log_test("POST /optimization", "PASS", f"Recommendations: {len(r.json()['recommendations'])}")
        else:
            log_test("POST /optimization", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 10. Scenario Analysis
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 10. Scenario Analysis ═══")

        r = await c.get("/api/v1/supply-chain/scenarios/types")
        if r.status_code == 200 and "scenarios" in r.json():
            log_test("GET /scenarios/types", "PASS", f"Types: {len(r.json()['scenarios'])}")
        else:
            log_test("GET /scenarios/types", "FAIL")

        r = await c.post("/api/v1/supply-chain/scenarios/simulate", json={
            "scenario_type": "supplier_failure",
            "parameters": {"supplier_name": "Test Supplier"},
        })
        if r.status_code == 200 and "impact" in r.json():
            log_test("POST /scenarios/simulate", "PASS", f"Scenario: {r.json()['name']}")
        else:
            log_test("POST /scenarios/simulate", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 11. Reports
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 11. Reports ═══")

        r = await c.post("/api/v1/supply-chain/reports/generate", json={"report_type": "full"})
        if r.status_code == 200 and "report_id" in r.json():
            log_test("POST /reports/generate", "PASS", f"Report: {r.json()['report_id'][:8]}...")
        else:
            log_test("POST /reports/generate", "FAIL")

        # ════════════════════════════════════════════════════════════════════════
        # 12. Error Handling
        # ════════════════════════════════════════════════════════════════════════
        print("\n═══ 12. Error Handling ═══")

        r = await c.get(f"/api/v1/supply-chain/suppliers/{uuid.uuid4()}")
        if r.status_code == 404:
            log_test("404 for invalid supplier", "PASS")
        else:
            log_test("404 for invalid supplier", "FAIL", f"Status: {r.status_code}")

        r = await c.post("/api/v1/supply-chain/scenarios/simulate", json={
            "scenario_type": "invalid_type",
        })
        if r.status_code == 400:
            log_test("400 for invalid scenario", "PASS")
        else:
            log_test("400 for invalid scenario", "FAIL", f"Status: {r.status_code}")

        # ════════════════════════════════════════════════════════════════════════
        # Summary
        # ════════════════════════════════════════════════════════════════════════
        print("\n" + "=" * 60)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        total = len(results)
        print(f"\n📊 TEST RESULTS: {passed}/{total} passed, {failed} failed")
        print("=" * 60)

        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in results:
                if r["status"] == "FAIL":
                    print(f"  - {r['name']}: {r['detail']}")


if __name__ == "__main__":
    asyncio.run(test_all_endpoints())
