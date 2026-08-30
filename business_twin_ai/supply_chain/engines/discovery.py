"""Trade-route scenario discovery — news → actionable route scenarios.

Scans live headlines (NewsAPI.org key → GDELT → curated pool) for each known
maritime chokepoint, classifies the threat (war/piracy/disaster/sanctions/
congestion/grounding), and scores how badly the route is affected. The result
feeds the Route Diversion simulator's "Live Risk Radar", the Market Watch
"Trade Route Alerts" section, and Dashboard alerts — so a trader can see
today's risk hotspots with one click to apply the scenario on the world map.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from business_twin_ai.services.news.gdelt import fetch_market_news
from business_twin_ai.supply_chain.engines.routes import CHOKEPOINTS

logger = logging.getLogger(__name__)

# Per-chokepoint news queries — tuned to surface disruption headlines.
CHOKEPOINT_QUERIES: Dict[str, str] = {
    "suez_canal": "Suez Canal shipping disruption container",
    "red_sea": "Red Sea Houthi attacks shipping",
    "bab_el_mandeb": "Bab el-Mandeb strait shipping attacks",
    "gulf_of_aden": "Gulf of Aden piracy shipping",
    "strait_of_hormuz": "Strait of Hormuz oil tanker conflict",
    "malacca_strait": "Malacca Strait piracy shipping",
    "panama_canal": "Panama Canal drought transits",
    "eu_asia_rail": "Trans-Siberian railway freight disruption",
    "us_land_bridge": "US rail freight delays intermodal",
}

# Keyword → event type classification (checked in priority order).
EVENT_KEYWORDS: List[tuple] = [
    ("war_conflict", ["war", "conflict", "attack", "missile", "drone", "airstrike", "military", "strike", "tension", "hostilities", "bomb"]),
    ("piracy", ["piracy", "pirate", "hijack", "seizure", "armed robbery", "ransom", "boarding"]),
    ("natural_disaster", ["storm", "typhoon", "hurricane", "earthquake", "flood", "cyclone", "monsoon", "tsunami"]),
    ("sanctions", ["sanction", "embargo", "blockade", "tariff", "ban", "restriction", "boycott"]),
    ("congestion", ["congestion", "drought", "transit", "backlog", "queue", "low water", "draft limit", "capacity"]),
    ("grounding", ["grounding", "collision", "accident", "aground", "strand", "fire", "explosion", "sink"]),
]

# Risk keywords that escalate a scenario's severity.
_ESCALATE = ["suspend", "halt", "shut", "close", "evacuate", "emergency", "warn", "alert", "fear", "disrupt", "delay", "crisis", "red sea", "hormuz"]
_DEESCALATE = ["resume", "reopen", "restore", "ease", "calm", "recover", "normal", "lift"]

# Severity weight of each chokepoint (matches CHOKEPOINTS metadata).
_SEVERITY_BASE = {"critical": 45, "high": 30, "medium": 15}

# Event type severity contribution (how bad each event is for trade routes).
_EVENT_WEIGHT = {
    "war_conflict": 35,
    "piracy": 20,
    "sanctions": 30,
    "natural_disaster": 20,
    "congestion": 10,
    "grounding": 25,
}

_EVENT_LABELS = {
    "war_conflict": "War / Conflict",
    "piracy": "Piracy / Attacks",
    "sanctions": "Sanctions / Blockade",
    "natural_disaster": "Natural Disaster",
    "congestion": "Congestion / Drought",
    "grounding": "Grounding / Accident",
}

_DEFAULT_SCENARIO: Dict[str, Any] = {
    "scenario_id": "route-risk-unknown",
    "chokepoint_id": "suez_canal",
    "chokepoint_name": "Suez Canal",
    "region": "Red Sea",
    "event_type": "congestion",
    "event_label": "Congestion / Drought",
    "severity": "medium",
    "risk_score": 30.0,
    "headline": "Global shipping routes face elevated chokepoint risk this quarter",
    "source": "Lloyd's List",
    "url": "https://news.google.com/search?q=shipping+chokepoint+risk",
    "published_at": None,
    "summary": "Baseline chokepoint risk — monitor live news for the latest status.",
}

# A realistic lane per chokepoint so "Apply & simulate" actually diverts the
# user's current voyage instead of blocking a chokepoint their route avoids.
# Suez and Panama use pairs whose baseline genuinely passes the chokepoint
# (Shanghai→Rotterdam and LA→NY now prefer the land bridges, so those pairs
# are used for the rail corridors instead).
CHOKEPOINT_ROUTES: Dict[str, Dict[str, str]] = {
    "suez_canal": {"origin": "singapore", "destination": "rotterdam"},
    "red_sea": {"origin": "mumbai", "destination": "piraeus"},
    "bab_el_mandeb": {"origin": "mumbai", "destination": "rotterdam"},
    "gulf_of_aden": {"origin": "singapore", "destination": "piraeus"},
    "strait_of_hormuz": {"origin": "jebel_ali", "destination": "mumbai"},
    "malacca_strait": {"origin": "shanghai", "destination": "colombo"},
    "panama_canal": {"origin": "valparaiso", "destination": "new_york"},
    "eu_asia_rail": {"origin": "shanghai", "destination": "hamburg"},
    "us_land_bridge": {"origin": "los_angeles", "destination": "new_york"},
}


def _classify_event(title: str, description: str = "") -> str:
    """Classify a headline into an event type from keyword rules."""
    text = f"{title} {description}".lower()
    for event_type, words in EVENT_KEYWORDS:
        if any(w in text for w in words):
            return event_type
    return "congestion"


def _score_headline(title: str, chokepoint: Dict[str, Any], event_type: str) -> float:
    """0–100 risk score for a single headline on a chokepoint."""
    text = title.lower()
    base = _SEVERITY_BASE.get(chokepoint.get("severity", "medium"), 15)
    score = base + _EVENT_WEIGHT.get(event_type, 10)
    score += 8 * sum(1 for w in _ESCALATE if w in text)
    score -= 12 * sum(1 for w in _DEESCALATE if w in text)
    return round(max(5.0, min(98.0, float(score))), 1)


def _severity_for(score: float) -> str:
    if score >= 70:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _is_curated(article: Dict[str, Any]) -> bool:
    """Curated fallback headlines always point at news.google.com search URLs."""
    return str(article.get("url", "")).startswith("https://news.google.com")


def _build_scenario(
    chokepoint_id: str,
    meta: Dict[str, Any],
    articles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Collapse fetched headlines for one chokepoint into a single scenario."""
    # fetch_market_news always returns content (curated pool fills gaps), so the
    # article list is never truly empty — but be defensive anyway.
    if not articles:
        headline = _DEFAULT_SCENARIO["headline"]
        source = _DEFAULT_SCENARIO["source"]
        url = _DEFAULT_SCENARIO["url"]
        published = None
        score = float(_SEVERITY_BASE.get(meta.get("severity", "medium"), 15))
        event_type = "congestion"
        is_live = False
    else:
        # Pick the strongest headline and score it.
        headline = articles[0].get("title") or _DEFAULT_SCENARIO["headline"]
        source = articles[0].get("source") or "NewsAPI"
        url = articles[0].get("url") or _DEFAULT_SCENARIO["url"]
        published = articles[0].get("published_at")
        event_type = _classify_event(headline, "")
        score = _score_headline(headline, meta, event_type)
        is_live = any(not _is_curated(a) for a in articles)

    return {
        "scenario_id": f"route-risk-{chokepoint_id}",
        "chokepoint_id": chokepoint_id,
        "chokepoint_name": meta.get("name", chokepoint_id),
        "region": meta.get("region", ""),
        "event_type": event_type,
        "event_label": _EVENT_LABELS.get(event_type, event_type.replace("_", " ").title()),
        "severity": _severity_for(score),
        "risk_score": score,
        "headline": headline,
        "source": source,
        "url": url,
        "published_at": published,
        "live": is_live,
        "suggest_origin": CHOKEPOINT_ROUTES.get(chokepoint_id, {}).get("origin"),
        "suggest_destination": CHOKEPOINT_ROUTES.get(chokepoint_id, {}).get("destination"),
        "summary": (
            f"{meta.get('name', chokepoint_id)} ({meta.get('region', '')}): "
            f"{_EVENT_LABELS.get(event_type, event_type)} risk assessed from "
            f"{len(articles)} recent headline(s)."
        ),
    }


async def discover_route_scenarios(
    limit: int = 6,
    news_limit: int = 3,
) -> Dict[str, Any]:
    """Scan live news across all chokepoints and return ranked scenarios.

    Returns ``{mode, updated_at, scenarios}`` where ``mode`` is ``\"live\"``
    when any headline came from a live feed (NewsAPI/GDELT) or ``\"curated\"``
    when everything fell back to the offline pool.
    """
    import asyncio

    limit = max(1, min(int(limit), 10))

    async def one(chokepoint_id: str) -> Dict[str, Any]:
        meta = CHOKEPOINTS[chokepoint_id]
        try:
            articles = await fetch_market_news(
                CHOKEPOINT_QUERIES.get(chokepoint_id, chokepoint_id),
                limit=news_limit,
            )
        except Exception:  # noqa: BLE001 — never kill the whole radar
            articles = []
        return _build_scenario(chokepoint_id, meta, articles)

    results = await asyncio.gather(*(one(cp) for cp in CHOKEPOINTS))
    results.sort(key=lambda s: -s["risk_score"])

    # "live" only when at least one headline came from a real feed (NewsAPI /
    # GDELT), not the curated offline pool.
    mode = "live" if any(s.get("live") for s in results) else "curated"
    return {
        "mode": mode,
        "updated_at": datetime.now(timezone.utc),
        "scenarios": results[:limit],
    }
