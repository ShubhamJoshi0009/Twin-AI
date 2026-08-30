"""Tests for report generation + download endpoints (business + supply chain)."""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./test_report_{uuid.uuid4().hex[:8]}.db")
os.environ.setdefault("AUTO_SEED_DEMO", "true")


def _client():
    from fastapi.testclient import TestClient

    from business_twin_ai.app import app

    return TestClient(app)


def test_business_report_generate_and_download():
    """POST /reports/{twin}/generate then GET /reports/{id}/download serves the PDF."""
    with _client() as c:
        twin_id = c.get("/api/v1/digital-twins").json()[0]["id"]
        r = c.post(f"/api/v1/reports/{twin_id}/generate", json={})
        assert r.status_code == 200
        report_id = r.json()["report_id"]
        assert r.json()["download_url"] == f"/api/v1/reports/{report_id}/download"

        d = c.get(f"/api/v1/reports/{report_id}/download")
        assert d.status_code == 200
        assert d.headers["content-type"] == "application/pdf"
        assert d.content.startswith(b"%PDF")


def test_supply_chain_report_generate_and_download():
    """POST /supply-chain/reports/generate then GET .../{id}/download serves the PDF."""
    with _client() as c:
        r = c.post("/api/v1/supply-chain/reports/generate", json={"report_type": "full"})
        assert r.status_code == 200
        report_id = r.json()["report_id"]

        d = c.get(f"/api/v1/supply-chain/reports/{report_id}/download")
        assert d.status_code == 200
        assert d.headers["content-type"] == "application/pdf"
        assert d.content.startswith(b"%PDF")


def test_download_missing_report_returns_404():
    with _client() as c:
        r = c.get(f"/api/v1/reports/{uuid.uuid4()}/download")
        assert r.status_code == 404
