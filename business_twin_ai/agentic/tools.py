"""Tool registry for the agentic layer.

Each tool has a name, a description (used by the LLM planner when a key is
configured), and an async executor that returns a plain dict. Tools read from
the live database and the news service, so every agent has real context.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.engines.health import HealthEngine
from business_twin_ai.core.engines.simulator import VALID_DECISIONS, SimulatorEngine
from business_twin_ai.core.schemas.schemas import DecisionRequest
from business_twin_ai.services.news.gdelt import fetch_market_news
from business_twin_ai.supply_chain.engines.discovery import discover_route_scenarios
from business_twin_ai.supply_chain.engines.routes import RouteDiversionEngine
from business_twin_ai.supply_chain.models.database import (
    InventoryItem,
    Shipment,
    Supplier,
    SupplyChainAlert,
    SupplyChainRisk,
)

logger = logging.getLogger(__name__)

ToolExecutor = Callable[..., Awaitable[Dict[str, Any]]]


class Tool:
    """A callable tool an agent can invoke, with metadata for the LLM planner."""

    def __init__(self, name: str, description: str, executor: ToolExecutor) -> None:
        self.name = name
        self.description = description
        self.executor = executor


async def _tool_twin_state(db: AsyncSession, twin_id: uuid.UUID) -> Dict[str, Any]:
    engine = DigitalTwinEngine(db)
    twin = await engine.get_twin(twin_id)
    if not twin:
        return {"error": f"twin {twin_id} not found"}
    return engine.get_twin_state(twin)


async def _tool_health(db: AsyncSession, twin_id: uuid.UUID) -> Dict[str, Any]:
    engine = HealthEngine(db)
    try:
        health = await engine.calculate_health(twin_id)
        return health.model_dump()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


async def _tool_simulate(db: AsyncSession, twin_id: uuid.UUID, decision_type: str, decision_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    engine = SimulatorEngine(db)
    try:
        sim = await engine.run_simulation(
            twin_id, DecisionRequest(decision_type=decision_type, decision_params=decision_params or {})
        )
        return {
            "decision_type": sim.decision_type,
            "predicted_revenue": sim.predicted_revenue,
            "predicted_profit": sim.predicted_profit,
            "confidence_score": sim.confidence_score,
            "recommendation": (sim.recommendation or {}).get("recommendation", ""),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


async def _tool_news(db: AsyncSession, query: str, limit: int = 6) -> Dict[str, Any]:
    articles = await fetch_market_news(query, limit=limit)
    return {"articles": articles, "count": len(articles)}


async def _tool_suppliers(db: AsyncSession) -> Dict[str, Any]:
    suppliers = (await db.execute(select(Supplier).where(Supplier.is_active == True))).scalars().all()  # noqa: E712
    return {
        "total": len(suppliers),
        "high_risk": [s.name for s in suppliers if s.risk_score > 60],
        "avg_reliability": round(sum(s.reliability_score for s in suppliers) / max(len(suppliers), 1), 2),
        "list": [
            {"name": s.name, "location": s.location, "risk_score": s.risk_score, "reliability": s.reliability_score}
            for s in suppliers
        ],
    }


async def _tool_inventory(db: AsyncSession) -> Dict[str, Any]:
    items = (await db.execute(select(InventoryItem))).scalars().all()
    return {
        "total_units": sum(i.current_stock for i in items),
        "low_stock": [i.product_name for i in items if i.current_stock <= i.reorder_level],
        "overstock": [i.product_name for i in items if i.current_stock > i.max_stock * 0.9],
        "anomalies": len([i for i in items if i.current_stock <= i.safety_stock]),
    }


async def _tool_shipments(db: AsyncSession) -> Dict[str, Any]:
    shipments = (await db.execute(select(Shipment))).scalars().all()
    return {
        "total": len(shipments),
        "in_transit": len([s for s in shipments if s.status == "in_transit"]),
        "delayed": [s.shipment_number for s in shipments if s.status == "delayed"],
        "transport_cost": round(sum(s.transport_cost for s in shipments), 2),
    }


async def _tool_risks(db: AsyncSession) -> Dict[str, Any]:
    risks = (await db.execute(select(SupplyChainRisk).where(SupplyChainRisk.status == "active").limit(10))).scalars().all()  # noqa: E712
    return {
        "total": len(risks),
        "list": [
            {"type": r.risk_type, "title": r.title, "severity": r.severity, "score": r.risk_score, "mitigation": r.mitigation}
            for r in risks
        ],
    }


async def _tool_alerts(db: AsyncSession) -> Dict[str, Any]:
    alerts = (await db.execute(select(SupplyChainAlert).where(SupplyChainAlert.status == "active").limit(10))).scalars().all()  # noqa: E712
    return {"total": len(alerts), "list": [{"title": a.title, "severity": a.severity} for a in alerts]}


def _tool_routes(db: AsyncSession, origin: str, destination: str, blocked_chokepoints: Optional[list] = None) -> Dict[str, Any]:
    """Synchronous wrapper over the RouteDiversionEngine."""
    engine = RouteDiversionEngine()
    try:
        return engine.simulate(
            origin=origin,
            destination=destination,
            blocked_chokepoints=blocked_chokepoints or [],
            event_type="war_conflict",
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


async def _tool_route_risk(db: AsyncSession, limit: int = 5) -> Dict[str, Any]:
    """Live trade-route risk radar — news-driven chokepoint scenarios.

    Scans today's headlines (NewsAPI → GDELT → curated pool) for every maritime
    chokepoint and returns the ranked risk scenarios so agents can cite real,
    current route threats (e.g. "Strait of Hormuz · critical · 88/100").
    """
    try:
        result = await discover_route_scenarios(limit=max(1, min(int(limit), 8)), news_limit=3)
        scenarios = result.get("scenarios", [])
        return {
            "mode": result.get("mode", "curated"),
            "count": len(scenarios),
            "top_risks": [
                {
                    "chokepoint": s["chokepoint_name"],
                    "chokepoint_id": s["chokepoint_id"],
                    "region": s["region"],
                    "event": s["event_label"],
                    "severity": s["severity"],
                    "risk_score": s["risk_score"],
                    "headline": s["headline"],
                }
                for s in scenarios[:limit]
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "count": 0, "top_risks": []}


def build_tools(db: AsyncSession) -> Dict[str, Tool]:
    """Create the tool registry bound to a database session."""
    tools = {
        "twin_state": Tool("twin_state", "Current financial and operational state of the digital twin", lambda twin_id: _tool_twin_state(db, twin_id)),
        "health": Tool("health", "Business health score breakdown (categories, trend, suggestions)", lambda twin_id: _tool_health(db, twin_id)),
        "simulate": Tool("simulate", f"Run a decision simulation. Valid decisions: {', '.join(sorted(VALID_DECISIONS))}. Params: decision_type, decision_params", lambda twin_id, dt, params=None: _tool_simulate(db, twin_id, dt, params)),
        "news": Tool("news", "Fetch the latest market news for a topic (e.g. 'Red Sea shipping', 'organic food retail')", lambda query, limit=6: _tool_news(db, query, limit)),
        "suppliers": Tool("suppliers", "List suppliers with risk scores and reliability", lambda: _tool_suppliers(db)),
        "inventory": Tool("inventory", "Inventory levels, low-stock and overstock items", lambda: _tool_inventory(db)),
        "shipments": Tool("shipments", "Shipment status, delays and transport costs", lambda: _tool_shipments(db)),
        "risks": Tool("risks", "Active supply chain risks with severities and mitigations", lambda: _tool_risks(db)),
        "alerts": Tool("alerts", "Active supply chain alerts", lambda: _tool_alerts(db)),
        "routes": Tool("routes", "Simulate a shipping route diversion (origin, destination, blocked_chokepoints)", lambda origin, destination, blocked=None: _tool_routes(db, origin, destination, blocked)),
        "route_risk": Tool("route_risk", "Live trade-route risk radar — today's chokepoint disruptions with severity and risk scores (e.g. Suez, Hormuz, Panama)", lambda limit=5: _tool_route_risk(db, limit)),

    }
    return tools
