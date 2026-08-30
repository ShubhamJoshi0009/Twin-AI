"""API routes for data seeding — powers the Settings → Data & Seeding UI.

Endpoints
---------
- GET  /api/v1/system/seed/status    — is there data in the database?
- POST /api/v1/system/seed           — apply the demo dataset or a custom
                                        payload (same format as the custom JSON
                                        data file used by the CLI seeder)
- GET  /api/v1/system/seed/template  — download the custom-data template
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.config import settings
from business_twin_ai.core.models.database import DigitalTwin
from business_twin_ai.core.schemas.schemas import BusinessData
from business_twin_ai.database import get_db
from business_twin_ai.seed import normalize_custom_data, seed_database

router = APIRouter(prefix="/system/seed", tags=["System / Seeding"])

# NOTE: POST /system/seed is destructive when `force=true` (it replaces all
# existing data). Gate it behind settings.ENABLE_SEED_API and treat it as an
# admin action in any deployed environment.


class SeedRequest(BaseModel):
    """Apply a dataset to the database.

    ``data`` may be the full custom-data payload (``business`` / ``simulations``
    / ``supply_chain`` sections, or a bare business object) — ``null`` seeds the
    built-in demo dataset.
    """

    data: Optional[Dict[str, Any]] = None
    force: bool = False


class SeedStatusResponse(BaseModel):
    """Whether the database currently contains data."""

    has_data: bool
    twin_count: int


@router.get("/status", response_model=SeedStatusResponse)
async def seed_status(db: AsyncSession = Depends(get_db)) -> SeedStatusResponse:
    """Report whether the database has been seeded."""
    count = (await db.execute(select(func.count()).select_from(DigitalTwin))).scalar() or 0
    return SeedStatusResponse(has_data=count > 0, twin_count=count)


@router.post("")
async def apply_seed(payload: SeedRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Seed the database with the demo dataset or a custom payload."""
    if not settings.ENABLE_SEED_API:
        raise HTTPException(
            status_code=403,
            detail="Seeding API is disabled — set ENABLE_SEED_API=true in the backend config to enable it.",
        )

    custom: Optional[Dict[str, Any]] = None
    if payload.data is not None:
        try:
            custom = normalize_custom_data(payload.data)
            # Early schema validation so malformed business data returns 422
            # (not a 500) before any rows are touched.
            BusinessData(**custom["business"])
        except (ValueError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                detail = "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
                )
            else:
                detail = str(exc)
            raise HTTPException(status_code=422, detail=f"Invalid custom data — {detail}")

    try:
        return await seed_database(db, force=payload.force, custom_data=custom)
    except ValueError as exc:
        # e.g. inventory provided without any warehouses — data is structurally
        # incomplete, so treat it as a client error, not a 500.
        raise HTTPException(status_code=422, detail=f"Invalid custom data — {exc}")


@router.get("/template")
async def seed_template() -> Dict[str, Any]:
    """Return the custom-data template (``demo_data.example.json``) so users can
    download it, fill in their own numbers, and re-upload it."""
    path = Path(__file__).resolve().parents[3] / "demo_data.example.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    return json.loads(path.read_text(encoding="utf-8"))
