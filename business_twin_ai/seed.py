"""Database seeder — populates the application with a ready-to-explore demo dataset.

Why this exists
---------------
Out of the box the database is empty, so a fresh install shows no data until the
user manually creates digital twins and supply chain records. This module seeds a
complete, coherent demo dataset (business twin + simulation history + supply
chain) on first startup so every screen of the platform is immediately usable.

Customising the data ("specific demands")
-----------------------------------------
Drop a JSON file (see ``demo_data.example.json`` in the repo root) and point the
app at it — either with the ``CUSTOM_DATA_FILE`` env var or the ``--file`` CLI
flag. The seeder will use your business profile and supply chain instead of the
built-in sample dataset. The file format:

.. code-block:: json

    {
      "business": { ...same shape as BusinessData schema... },
      "simulations": [ { "decision_type": "...", "decision_params": {...}, ... } ],
      "supply_chain": {
        "suppliers":  [ {...} ],
        "warehouses": [ {...} ],
        "inventory":  [ {...} ],
        "shipments":  [ {...} ]
      }
    }

The individual supplier / warehouse / inventory / shipment entries accept the
same fields as the sample data in ``business_twin_ai/supply_chain/sample_data.py``.

CLI usage
---------
    python -m business_twin_ai.seed                 # seed only if the DB is empty
    python -m business_twin_ai.seed --force         # wipe demo data and reseed
    python -m business_twin_ai.seed --file my.json  # seed from a custom data file
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Import every model module so all tables register on Base.metadata before
# init_db() runs (otherwise create_all would silently miss tables).
from business_twin_ai.config import settings
from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.engines.simulator import SimulatorEngine
from business_twin_ai.core.engines.source_checklist import SourceChecklistEngine
from business_twin_ai.core.models.database import (
    DigitalTwin,
    Insight,
    ProfileChecklist,
    Simulation,
    Strategy,
)
from business_twin_ai.core.schemas.schemas import BusinessData, DecisionRequest
from business_twin_ai.database import async_session_factory, init_db
from business_twin_ai.sample_data import (
    SAMPLE_BUSINESS_DATA,
    SAMPLE_SIMULATION_HISTORY,
)
from business_twin_ai.supply_chain.engines.alerts import AlertEngine
from business_twin_ai.supply_chain.models.database import (
    InventoryItem,
    Shipment,
    Supplier,
    SupplyChainAlert,
    SupplyChainRisk,
    SupplyChainScenario,
    Warehouse,
)
from business_twin_ai.supply_chain.sample_data import (
    SAMPLE_INVENTORY,
    SAMPLE_SHIPMENTS,
    SAMPLE_SUPPLIERS,
    SAMPLE_WAREHOUSES,
)

logger = logging.getLogger(__name__)

# Table deletion order for --force (children first, so FK constraints hold).
_FORCE_DELETE_ORDER = [
    Shipment,
    InventoryItem,
    SupplyChainRisk,
    SupplyChainAlert,
    SupplyChainScenario,
    Warehouse,
    Supplier,
    ProfileChecklist,
    Insight,
    Strategy,
    Simulation,
    DigitalTwin,
]


# ═══════════════════════════════════════════════════════════════════════════════
# Custom data loading
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_custom_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a raw custom-data dict into a ``{business, simulations,
    supply_chain}`` structure.

    Accepts either the full file format documented above, or a bare business
    JSON object (kept as ``business``) for maximum flexibility.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"Custom data must be a JSON object, got {type(raw).__name__}")

    if "business" in raw:
        business: Dict[str, Any] = raw["business"]
        simulations = raw.get("simulations", [])
        supply_chain = raw.get("supply_chain", {})
    else:
        # Bare BusinessData object — no simulations / supply chain provided.
        business = raw
        simulations = []
        supply_chain = {}

    if not isinstance(business, dict):
        raise ValueError("'business' section must be a JSON object")
    if not isinstance(simulations, list):
        raise ValueError("'simulations' section must be a JSON array")
    if not isinstance(supply_chain, dict):
        raise ValueError("'supply_chain' section must be a JSON object")

    return {
        "business": business,
        "simulations": simulations,
        "supply_chain": supply_chain,
    }


def load_custom_data(path: str | Path) -> Dict[str, Any]:
    """Load and normalise a custom data file into a ``{business, simulations,
    supply_chain}`` structure."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Custom data file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    return normalize_custom_data(raw)


def _resolve_custom_data(custom_file: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return custom data from CLI arg / env var, or None to use sample data."""
    path = custom_file or settings.CUSTOM_DATA_FILE
    if not path:
        return None
    return load_custom_data(path)


# ═══════════════════════════════════════════════════════════════════════════════
# Supplier scoring helpers (mirror the SupplierEngine formulas so the demo
# dataset is internally consistent with live-created records)
# ═══════════════════════════════════════════════════════════════════════════════

def _reliability_score(data: Dict[str, Any]) -> float:
    score = 50.0
    quality = data.get("quality_rating", 0) or 0
    lead_time = data.get("lead_time_days", 7) or 7
    capacity = data.get("capacity", 0) or 0
    if quality >= 4:
        score += 20
    elif quality >= 3:
        score += 10
    if lead_time <= 7:
        score += 15
    elif lead_time <= 14:
        score += 5
    if capacity >= 1000:
        score += 10
    return round(min(100, max(0, score)), 1)


def _risk_score(data: Dict[str, Any]) -> float:
    risk = 30.0
    if (data.get("lead_time_days", 0) or 0) > 14:
        risk += 20
    if (data.get("quality_rating", 0) or 0) < 3:
        risk += 25
    if (data.get("capacity", 0) or 0) < 500:
        risk += 15
    return round(min(100, max(0, risk)), 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Seeding
# ═══════════════════════════════════════════════════════════════════════════════

async def seed_database(
    db: AsyncSession,
    *,
    force: bool = False,
    custom_file: Optional[str] = None,
    custom_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Seed the database with demo data.

    Idempotent: when the DB already contains digital twins the seed is skipped
    (unless ``force=True``). ``custom_file`` loads custom data from a JSON file;
    ``custom_data`` accepts an already-normalised ``{business, simulations,
    supply_chain}`` dict (used by the seeding API). Returns a summary of what
    was created.
    """
    custom = custom_data if custom_data is not None else _resolve_custom_data(custom_file)
    if custom is None:
        # No custom profile → seed the built-in demo dataset in full.
        business_data = dict(SAMPLE_BUSINESS_DATA)
        simulations = SAMPLE_SIMULATION_HISTORY
        suppliers = SAMPLE_SUPPLIERS
        warehouses = SAMPLE_WAREHOUSES
        inventory = SAMPLE_INVENTORY
        shipments = SAMPLE_SHIPMENTS
    else:
        # Custom profile → use exactly what was provided (no silent merge with
        # demo entities, so the UI preview always matches the result).
        business_data = custom["business"]
        simulations = custom["simulations"]
        sc = custom["supply_chain"] or {}
        suppliers = sc.get("suppliers") or []
        warehouses = sc.get("warehouses") or []
        inventory = sc.get("inventory") or []
        shipments = sc.get("shipments") or []

    existing = (await db.execute(select(func.count()).select_from(DigitalTwin))).scalar() or 0
    if existing > 0 and not force:
        return {
            "skipped": True,
            "reason": "database already contains data (use --force to reseed, e.g. with your custom file)",
        }

    if force:
        for model in _FORCE_DELETE_ORDER:
            await db.execute(delete(model))

    # ── 1. Digital twin ──────────────────────────────────────────────────────
    twin_engine = DigitalTwinEngine(db)
    twin = await twin_engine.create_twin(BusinessData(**business_data))
    twin.business_health_score = 72.0

    # ── 2. Simulation history (feeds the timeline) ───────────────────────────
    # Run each through the real simulator pipeline so every record carries the
    # full predictions / scenarios / confidence / recommendation / explanation
    # payloads the API (and UI) expect.
    simulator = SimulatorEngine(db)
    sim_count = 0
    for sim in simulations:
        await simulator.run_simulation(
            twin.id,
            DecisionRequest(
                decision_type=sim.get("decision_type", "increase_marketing"),
                decision_params=sim.get("decision_params", {}) or {},
            ),
        )
        sim_count += 1

    # ── 3. Insights ──────────────────────────────────────────────────────────
    # All derived values are guarded so minimal custom profiles (e.g. no
    # marketing budget or customers yet) still seed cleanly.
    profit_margin_pct = round(twin.profit / twin.revenue * 100, 1) if twin.revenue else 0.0
    marketing_roi = round(twin.sales / twin.marketing_budget, 1) if twin.marketing_budget else 0.0
    revenue_per_customer = round(twin.revenue / twin.customers, 2) if twin.customers else 0.0
    insights_seeded = [
        {
            "insight_type": "profit_increase",
            "title": "Profit margin overview",
            "description": (
                f"{twin.name} is generating a {profit_margin_pct:.1f}% profit margin "
                f"on ${twin.revenue:,.0f} revenue."
            ),
            "severity": "info",
            "data": {"profit_margin": profit_margin_pct},
        },
        {
            "insight_type": "growth_opportunity",
            "title": "Marketing ROI headroom",
            "description": (
                f"Marketing ROI of {marketing_roi:.1f}x suggests room to scale "
                "high-performing channels."
            ),
            "severity": "info",
            "data": {"marketing_roi": marketing_roi},
        },
        {
            "insight_type": "customer",
            "title": "Customer base analysis",
            "description": (
                f"Average revenue per customer is ${revenue_per_customer:,.2f} across "
                f"{twin.customers:,} customers — a retention program could lift it further."
            ),
            "severity": "warning",
            "data": {
                "revenue_per_customer": revenue_per_customer,
                "total_customers": twin.customers,
            },
        },
    ]
    for ins in insights_seeded:
        db.add(Insight(twin_id=twin.id, **ins))

    # ── 3b. Completed sample checklist record ────────────────────────────────
    # Demonstrate the saved state: the demo twin ships with a fully audited,
    # all-sections-complete source checklist so users see a finished record
    # (coverage + completion) on first run.
    checklist_engine = SourceChecklistEngine(db)
    checklist = await checklist_engine.build_checklist(twin.id)
    if checklist is not None:
        completions = {item.source_id: True for item in checklist.items}
        await checklist_engine.save_completions(twin.id, completions)
        # Seed the audit snapshot too, so a fresh install already has a
        # regression baseline and a populated `last_audited_at` on the
        # cross-profile overview.
        saved_row = (
            await db.execute(
                select(ProfileChecklist).where(ProfileChecklist.twin_id == twin.id)
            )
        ).scalar_one_or_none()
        if saved_row is not None:
            saved_row.last_audit_coverage = checklist.overall_coverage
            saved_row.last_audit_verified = checklist.verified_count
            saved_row.last_audited_at = datetime.now(timezone.utc)

    # ── 4. Supply chain ──────────────────────────────────────────────────────
    sup_objs: List[Supplier] = []
    for s in suppliers:
        sup = Supplier(
            name=s["name"],
            contact_name=s.get("contact_name"),
            email=s.get("email"),
            location=s.get("location"),
            country=s.get("country"),
            product_categories=s.get("product_categories", []) or [],
            lead_time_days=s.get("lead_time_days", 7),
            cost_per_unit=s.get("cost_per_unit", 0.0),
            capacity=s.get("capacity", 1000),
            quality_rating=s.get("quality_rating", 5.0),
            contract_expiry=s.get("contract_expiry"),
            reliability_score=s.get("reliability_score", _reliability_score(s)),
            risk_score=s.get("risk_score", _risk_score(s)),
            is_active=True,
        )
        db.add(sup)
        sup_objs.append(sup)

    wh_objs: List[Warehouse] = []
    for w in warehouses:
        wh = Warehouse(
            name=w["name"],
            location=w.get("location", "Unknown"),
            capacity=w.get("capacity", 10000),
            utilization=w.get("utilization", 0.7),
            storage_cost_per_unit=w.get("storage_cost_per_unit", 0.5),
            efficiency_score=w.get("efficiency_score", 85.0),
            incoming_shipments=w.get("incoming_shipments", 0),
            outgoing_shipments=w.get("outgoing_shipments", 0),
            manager=w.get("manager"),
            is_active=True,
        )
        db.add(wh)
        wh_objs.append(wh)

    # Flush so suppliers/warehouses get their PKs before dependent rows
    # (inventory + shipments) reference them.
    await db.flush()

    inv_objs: List[InventoryItem] = []
    for idx, item in enumerate(inventory):
        warehouse = wh_objs[idx % len(wh_objs)] if wh_objs else None
        if warehouse is None:
            raise ValueError("Supply chain custom data must include at least one warehouse")
        inv = InventoryItem(
            warehouse_id=warehouse.id,
            product_name=item["product_name"],
            product_sku=item.get("product_sku", ""),
            category=item.get("category", "general"),
            current_stock=item.get("current_stock", 0),
            reorder_level=item.get("reorder_level", 100),
            safety_stock=item.get("safety_stock", 50),
            max_stock=item.get("max_stock", 5000),
            incoming_stock=item.get("incoming_stock", 0),
            reserved_stock=item.get("reserved_stock", 0),
            unit_cost=item.get("unit_cost", 0.0),
            turnover_rate=item.get("turnover_rate", 0.0),
            expiry_date=item.get("expiry_date"),
        )
        db.add(inv)
        inv_objs.append(inv)

    for idx, sh in enumerate(shipments):
        supplier = sup_objs[idx % len(sup_objs)] if sup_objs else None
        warehouse = wh_objs[idx % len(wh_objs)] if wh_objs else None
        if supplier is None or warehouse is None:
            raise ValueError("Supply chain custom data must include at least one supplier and warehouse")
        db.add(
            Shipment(
                supplier_id=supplier.id,
                warehouse_id=warehouse.id,
                shipment_number=sh.get("shipment_number", f"SHP-SEED-{idx + 1:04d}"),
                status=sh.get("status", "pending"),
                product_name=sh["product_name"],
                quantity=sh.get("quantity", 0),
                route=sh.get("route"),
                origin=sh.get("origin", ""),
                destination=sh.get("destination", ""),
                distance_km=sh.get("distance_km", 0.0),
                fuel_cost=sh.get("fuel_cost", 0.0),
                transport_cost=sh.get("transport_cost", 0.0),
                route_efficiency=sh.get("route_efficiency", 0.8),
                notes=sh.get("notes"),
            )
        )

    await db.flush()

    # ── 5. Alerts ────────────────────────────────────────────────────────────
    # Derive real operational alerts (low stock, delayed shipments, supplier
    # reliability, warehouse pressure) from the freshly seeded supply chain so
    # the notifications bell and the Alerts Center have live data on first run.
    alert_engine = AlertEngine(db)
    alert_objs = await alert_engine.generate_alerts()
    await db.flush()

    return {
        "skipped": False,
        "twin": {"id": str(twin.id), "name": twin.name},
        "counts": {
            "simulations": sim_count,
            "insights": len(insights_seeded),
            "suppliers": len(sup_objs),
            "warehouses": len(wh_objs),
            "inventory": len(inv_objs),
            "shipments": len(shipments),
            "alerts": len(alert_objs),
            "checklist_sections": (
                checklist.total_sections if checklist is not None else 0
            ),
        },
    }


async def run_seed(force: bool = False, custom_file: Optional[str] = None) -> Dict[str, Any]:
    """Standalone entrypoint: init tables, seed, commit."""
    await init_db()
    async with async_session_factory() as session:
        summary = await seed_database(session, force=force, custom_file=custom_file)
        await session.commit()
    return summary


def _print_summary(summary: Dict[str, Any]) -> None:
    if summary.get("skipped"):
        print(f"[SKIP] Seed skipped — {summary['reason']}")
        return
    counts = summary["counts"]
    twin = summary["twin"]
    print(f"[OK] Seeded digital twin: {twin['name']} ({twin['id']})")
    print(
        "[OK] Created "
        f"{counts['simulations']} simulations, "
        f"{counts['insights']} insights, "
        f"{counts['suppliers']} suppliers, "
        f"{counts['warehouses']} warehouses, "
        f"{counts['inventory']} inventory items, "
        f"{counts['shipments']} shipments, "
        f"{counts.get('alerts', 0)} alerts"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Business Twin AI with demo data.")
    parser.add_argument("--force", action="store_true", help="Wipe demo data and reseed")
    parser.add_argument(
        "--file",
        default=None,
        help="Path to a custom JSON data file (overrides CUSTOM_DATA_FILE env var)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    try:
        summary = asyncio.run(run_seed(force=args.force, custom_file=args.file))
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    _print_summary(summary)


if __name__ == "__main__":
    main()
