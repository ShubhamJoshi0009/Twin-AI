"""Route Diversion Simulator engine.

Models a simplified world shipping network (major ports + sea lanes with
chokepoints like the Suez Canal, Strait of Hormuz, Malacca Strait, Panama
Canal). When a lane is blocked — by war, piracy, natural disaster, sanctions,
or congestion — the engine re-routes traffic with Dijkstra's shortest-path
algorithm and quantifies the impact (extra distance, days, cost, risk).

The network is intentionally compact (~24 ports, ~38 lanes) so the simulator
runs instantly and is easy to render on a world map in the UI.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── World network data ────────────────────────────────────────────────────────

PORT_COORDS: Dict[str, Dict[str, Any]] = {
    # Asia / Pacific
    "shanghai":    {"name": "Shanghai",    "lat": 31.23, "lng": 121.47, "region": "East Asia"},
    "singapore":   {"name": "Singapore",   "lat": 1.35,  "lng": 103.82, "region": "SE Asia"},
    "colombo":     {"name": "Colombo",     "lat": 6.93,  "lng": 79.85,  "region": "South Asia"},
    "mumbai":      {"name": "Mumbai",      "lat": 18.94, "lng": 72.83,  "region": "South Asia"},
    "karachi":     {"name": "Karachi",     "lat": 24.86, "lng": 67.00,  "region": "South Asia"},
    "muscat":      {"name": "Muscat",      "lat": 23.59, "lng": 58.41,  "region": "Middle East"},
    "jebel_ali":   {"name": "Jebel Ali",   "lat": 25.01, "lng": 55.05,  "region": "Middle East"},
    "bandar_abbas": {"name": "Bandar Abbas", "lat": 27.18, "lng": 56.28, "region": "Middle East"},
    "aden":        {"name": "Aden",        "lat": 12.78, "lng": 45.03,  "region": "Red Sea"},
    "djibouti":    {"name": "Djibouti",    "lat": 11.59, "lng": 43.15,  "region": "Red Sea"},
    "suez":        {"name": "Port Suez",   "lat": 29.97, "lng": 32.55,  "region": "Red Sea"},
    "port_said":   {"name": "Port Said",   "lat": 31.27, "lng": 32.30,  "region": "Mediterranean"},
    # Europe / Africa
    "piraeus":     {"name": "Piraeus",     "lat": 37.94, "lng": 23.65,  "region": "Mediterranean"},
    "rotterdam":   {"name": "Rotterdam",   "lat": 51.92, "lng": 4.48,   "region": "North Europe"},
    "hamburg":     {"name": "Hamburg",     "lat": 53.55, "lng": 9.99,   "region": "North Europe"},
    "casablanca":  {"name": "Casablanca",  "lat": 33.57, "lng": -7.59,  "region": "West Africa"},
    "dakar":       {"name": "Dakar",       "lat": 14.69, "lng": -17.44, "region": "West Africa"},
    "cape_town":   {"name": "Cape Town",   "lat": -33.92, "lng": 18.42, "region": "South Africa"},
    "mombasa":     {"name": "Mombasa",     "lat": -4.04, "lng": 39.66,  "region": "East Africa"},
    # Americas
    "new_york":    {"name": "New York",    "lat": 40.71, "lng": -74.01, "region": "North America"},
    "houston":     {"name": "Houston",     "lat": 29.76, "lng": -95.37, "region": "North America"},
    "panama_colon": {"name": "Colón (Panama)", "lat": 9.36, "lng": -79.90, "region": "Central America"},
    "panama_balboa": {"name": "Balboa (Panama)", "lat": 8.95, "lng": -79.57, "region": "Central America"},
    "los_angeles": {"name": "Los Angeles", "lat": 33.74, "lng": -118.27, "region": "North America"},
    "vancouver":   {"name": "Vancouver",   "lat": 49.28, "lng": -123.12, "region": "North America"},
    "valparaiso":  {"name": "Valparaíso",  "lat": -33.05, "lng": -71.62, "region": "South America"},
    "santos":      {"name": "Santos",      "lat": -23.96, "lng": -46.30, "region": "South America"},
    "buenos_aires": {"name": "Buenos Aires", "lat": -34.60, "lng": -58.38, "region": "South America"},
}

# Lanes: (from, to, label, chokepoint_id_or_None, distance_multiplier=1.0)
# Chokepoints mirror real-world pinch points. Land corridors (rail bridges)
# carry a circuity multiplier so their modelled distance matches reality —
# they stay competitive with sea routes for their corridor without
# dominating the whole network.
LANES: List[tuple] = [
    # East Asia ↔ SE Asia
    ("shanghai", "singapore", "South China Sea", None),
    ("shanghai", "vancouver", "North Pacific", None),
    ("shanghai", "los_angeles", "North Pacific", None),
    # Malacca
    ("singapore", "colombo", "Strait of Malacca", "malacca_strait"),
    # Indian Ocean
    ("colombo", "mumbai", "Arabian Sea", None),
    ("mumbai", "karachi", "Arabian Sea", None),
    ("karachi", "muscat", "Gulf of Oman", None),
    ("mumbai", "muscat", "Arabian Sea", None),
    # Gulf / Hormuz
    ("muscat", "jebel_ali", "Strait of Hormuz", "strait_of_hormuz"),
    ("jebel_ali", "bandar_abbas", "Persian Gulf", None),
    # Red Sea corridor
    ("muscat", "aden", "Gulf of Aden", "gulf_of_aden"),
    ("aden", "djibouti", "Bab el-Mandeb", "bab_el_mandeb"),
    ("djibouti", "suez", "Red Sea", "red_sea"),
    ("suez", "port_said", "Suez Canal", "suez_canal"),
    ("port_said", "piraeus", "Mediterranean", None),
    ("piraeus", "rotterdam", "Mediterranean / Gibraltar", None),
    ("piraeus", "casablanca", "Western Mediterranean", None),
    # Africa
    ("djibouti", "mombasa", "Indian Ocean (East Africa)", None),
    ("mombasa", "cape_town", "Mozambique Channel", None),
    ("casablanca", "dakar", "West Africa coast", None),
    ("dakar", "cape_town", "South Atlantic", None),
    ("cape_town", "santos", "South Atlantic", None),
    ("santos", "buenos_aires", "Rio de la Plata", None),
    ("santos", "dakar", "South Atlantic", None),
    # Land corridors (rail bridges)
    ("shanghai", "hamburg", "Trans-Siberian / Eurasian Rail", "eu_asia_rail", 1.6),
    ("los_angeles", "new_york", "US Transcontinental Rail", "us_land_bridge", 1.6),
    # Europe ↔ Americas
    ("rotterdam", "hamburg", "North Sea", None),
    ("rotterdam", "new_york", "North Atlantic", None),
    ("hamburg", "new_york", "North Atlantic", None),
    ("dakar", "houston", "Central Atlantic", None),
    ("dakar", "new_york", "Central Atlantic", None),
    ("houston", "new_york", "US Gulf / East Coast", None),
    ("houston", "panama_colon", "Caribbean Sea", None),
    ("new_york", "panama_colon", "North Atlantic / Caribbean", None),
    # Panama
    ("panama_colon", "panama_balboa", "Panama Canal", "panama_canal"),
    # Pacific Americas
    ("panama_balboa", "los_angeles", "East Pacific", None),
    ("panama_balboa", "valparaiso", "South Pacific", None),
    ("los_angeles", "vancouver", "West Coast N. America", None),
    ("valparaiso", "buenos_aires", "Cape Horn / South", None),
    ("vancouver", "singapore", "North Pacific", None),
]

# Chokepoint metadata: id → {name, region, description, severity, risk_multiplier}
CHOKEPOINTS: Dict[str, Dict[str, Any]] = {
    "suez_canal": {
        "name": "Suez Canal",
        "region": "Egypt",
        "description": "The Suez Canal carries ~12% of global trade. War, blockade or grounding can force ships around the Cape of Good Hope (+9,000 km).",
        "severity": "critical",
        "risk_multiplier": 3.0,
        "kind": "maritime",
        "solution": "Divert around the Cape of Good Hope — the standard alternative adds ~9,000 km and ~10 days. For Asia–North Europe cargo, the Eurasian land bridge is the fastest land fallback.",
    },
    "red_sea": {
        "name": "Red Sea",
        "region": "Red Sea / Yemen",
        "description": "Missile and drone attacks on commercial shipping have forced reroutes around Africa.",
        "severity": "critical",
        "risk_multiplier": 3.0,
        "kind": "maritime",
        "solution": "Reroute around the Cape of Good Hope (+9,000 km, ~+10 days) or trans-ship via the Gulf and the Eurasian land bridge for time-sensitive cargo.",
    },
    "bab_el_mandeb": {
        "name": "Bab el-Mandeb",
        "region": "Djibouti / Yemen",
        "description": "The 30km-wide strait linking the Red Sea and Gulf of Aden is a key chokepoint for Asia–Europe trade.",
        "severity": "high",
        "risk_multiplier": 2.5,
        "kind": "maritime",
        "solution": "Divert via the Cape of Good Hope, or use the Djibouti–Ethiopia rail corridor plus Gulf trans-shipment for regional cargo (+~8,000 km by sea).",
    },
    "gulf_of_aden": {
        "name": "Gulf of Aden",
        "region": "Somalia / Yemen",
        "description": "Piracy and armed conflict make this corridor risky for container traffic.",
        "severity": "high",
        "risk_multiplier": 2.0,
        "kind": "maritime",
        "solution": "Keep eastbound and westbound convoys apart — divert India–Europe flows via Muscat → Red Sea, and Asia–Europe via the Cape of Good Hope.",
    },
    "strait_of_hormuz": {
        "name": "Strait of Hormuz",
        "region": "Iran / Oman",
        "description": "Chokepoint for ~20% of global oil. Conflict here disrupts energy and container shipping.",
        "severity": "critical",
        "risk_multiplier": 3.0,
        "kind": "maritime",
        "solution": "Pump crude via the Saudi East–West (Petroline) pipeline to Yanbu on the Red Sea, or route around the Arabian Peninsula — ~+3,500 km, ~+5 days.",
    },
    "malacca_strait": {
        "name": "Strait of Malacca",
        "region": "Malaysia / Indonesia / Singapore",
        "description": "Busiest strait in the world; piracy and grounding risks delay Asia–Europe/Asia–Middle East flows.",
        "severity": "medium",
        "risk_multiplier": 1.8,
        "kind": "maritime",
        "solution": "Divert via the Sunda or Lombok straits east of Java — adds ~1,000–1,500 km and 1–2 days for ships able to take the deeper southern passages.",
    },
    "panama_canal": {
        "name": "Panama Canal",
        "region": "Panama",
        "description": "Drought restrictions and congestion reduce daily transits, adding weeks to Asia–US East Coast routes.",
        "severity": "medium",
        "risk_multiplier": 1.8,
        "kind": "maritime",
        "solution": "Divert via the Strait of Magellan / Cape Horn around South America, or re-route Asia–US Gulf cargo through the Suez Canal (+4,000–6,000 km, ~+5–8 days).",
    },
    "eu_asia_rail": {
        "name": "Eurasian Land Bridge",
        "region": "Trans-Siberian / Belt & Road corridor",
        "description": "The rail bridge linking Shanghai and North Europe carries high-value Asia–Europe cargo. Conflict, gauge disputes or congestion can sever the overland shortcut overnight.",
        "severity": "high",
        "risk_multiplier": 2.0,
        "kind": "land",
        "solution": "Fall back to ocean routes via the Suez Canal or Cape of Good Hope (+4,000–6,000 km, ~+6–9 days), or shift volume to the southern corridor via Colombo and the Red Sea.",
    },
    "us_land_bridge": {
        "name": "US Transcontinental Rail",
        "region": "United States (LA ↔ NYC)",
        "description": "Intermodal rail across the US moves Asia-origin cargo between West and East Coast ports faster than sailing around the continent.",
        "severity": "medium",
        "risk_multiplier": 1.6,
        "kind": "land",
        "solution": "Divert to all-water service through the Panama Canal or Cape Horn (+3,000–5,000 km, ~+4–7 days), or route via Gulf ports (Houston) with inland rail/road legs.",
    },
}

EVENT_TYPES: Dict[str, Dict[str, Any]] = {
    "war_conflict": {"label": "War / Conflict", "icon": "⚔️", "severity": "critical"},
    "piracy": {"label": "Piracy / Attacks", "icon": "🏴‍☠️", "severity": "high"},
    "natural_disaster": {"label": "Natural Disaster", "icon": "🌪️", "severity": "high"},
    "sanctions": {"label": "Sanctions / Blockade", "icon": "🚫", "severity": "critical"},
    "congestion": {"label": "Congestion / Drought", "icon": "🚢", "severity": "medium"},
    "grounding": {"label": "Grounding / Accident", "icon": "🧊", "severity": "high"},
}

# ── Graph helpers ─────────────────────────────────────────────────────────────

def _haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    """Great-circle distance in km between two coordinates."""
    r = 6371.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


@dataclass
class RouteSegment:
    """One lane traversal in a computed route."""

    from_port: str
    to_port: str
    lane: str
    chokepoint: Optional[str] = None
    distance_km: float = 0.0
    risk: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": PORT_COORDS[self.from_port]["name"],
            "to": PORT_COORDS[self.to_port]["name"],
            "lane": self.lane,
            "chokepoint": self.chokepoint,
            "distance_km": round(self.distance_km, 1),
            "risk": round(self.risk, 1),
        }


@dataclass
class RouteResult:
    """A computed route between two ports."""

    path: List[RouteSegment] = field(default_factory=list)
    total_km: float = 0.0
    total_risk: float = 0.0

    @property
    def empty(self) -> bool:
        return not self.path


class RouteDiversionEngine:
    """Simulates route blockages and computes diversions."""

    def __init__(self) -> None:
        # Build adjacency: port → [(neighbor, distance_km, lane, chokepoint)]
        # Land corridors carry a circuity multiplier so rail distances stay
        # realistic instead of being a straight great-circle line.
        self.graph: Dict[str, List[tuple]] = {p: [] for p in PORT_COORDS}
        for lane_entry in LANES:
            a, b, lane, chokepoint = lane_entry[:4]
            multiplier = float(lane_entry[4]) if len(lane_entry) > 4 else 1.0
            d = _haversine_km(
                PORT_COORDS[a]["lat"], PORT_COORDS[a]["lng"],
                PORT_COORDS[b]["lat"], PORT_COORDS[b]["lng"],
            ) * multiplier
            self.graph[a].append((b, d, lane, chokepoint))
            self.graph[b].append((a, d, lane, chokepoint))

    def network(self) -> Dict[str, Any]:
        """Full network description for the world-map UI."""
        ports = [
            {"id": pid, **PORT_COORDS[pid]}
            for pid in PORT_COORDS
        ]
        segments = []
        seen = set()
        for lane_entry in LANES:
            a, b, lane, chokepoint = lane_entry[:4]
            multiplier = float(lane_entry[4]) if len(lane_entry) > 4 else 1.0
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            segments.append({
                "id": f"{a}__{b}",
                "from": a,
                "to": b,
                "label": lane,
                "chokepoint": chokepoint,
                "distance_km": round(_haversine_km(
                    PORT_COORDS[a]["lat"], PORT_COORDS[a]["lng"],
                    PORT_COORDS[b]["lat"], PORT_COORDS[b]["lng"],
                ) * multiplier, 1),
            })
        chokepoints = [
            {"id": cid, **meta} for cid, meta in CHOKEPOINTS.items()
        ]
        return {"ports": ports, "segments": segments, "chokepoints": chokepoints}

    # ── Shortest path ──────────────────────────────────────────────────────

    def shortest_path(
        self,
        origin: str,
        destination: str,
        blocked_chokepoints: Optional[List[str]] = None,
    ) -> RouteResult:
        """Dijkstra shortest path (by distance) honoring blocked chokepoints.

        A lane is unusable when its chokepoint is blocked OR when the lane
        itself is a blocked chokepoint.
        """
        blocked = set(blocked_chokepoints or [])

        def lane_open(chokepoint: Optional[str]) -> bool:
            return not (chokepoint and chokepoint in blocked)

        # Dijkstra
        import heapq

        dist: Dict[str, float] = {origin: 0.0}
        prev: Dict[str, Optional[tuple]] = {origin: None}
        heap = [(0.0, origin)]
        while heap:
            d, node = heapq.heappop(heap)
            if d > dist.get(node, float("inf")):
                continue
            for neighbor, lane_km, lane, chokepoint in self.graph[node]:
                if not lane_open(chokepoint):
                    continue
                nd = d + lane_km
                if nd < dist.get(neighbor, float("inf")):
                    dist[neighbor] = nd
                    prev[neighbor] = (node, lane, chokepoint, lane_km)
                    heapq.heappush(heap, (nd, neighbor))

        if destination not in dist:
            return RouteResult()

        # Reconstruct path
        path: List[RouteSegment] = []
        node = destination
        while prev[node] is not None:
            pnode, lane, chokepoint, lane_km = prev[node]  # type: ignore[misc]
            path.append(RouteSegment(
                from_port=pnode, to_port=node, lane=lane,
                chokepoint=chokepoint, distance_km=lane_km,
            ))
            node = pnode
        path.reverse()

        total_risk = self._route_risk(path, blocked)
        return RouteResult(path=path, total_km=dist[destination], total_risk=total_risk)

    def _route_risk(
        self, path: List[RouteSegment], blocked: Optional[set] = None
    ) -> float:
        """Risk score 0–100 for a route (higher when it uses risky chokepoints)."""
        blocked = blocked or set()
        risk = 0.0
        for seg in path:
            if seg.chokepoint:
                meta = CHOKEPOINTS.get(seg.chokepoint, {})
                base = {"low": 10, "medium": 25, "high": 45, "critical": 65}.get(
                    meta.get("severity", "medium"), 25
                )
                if seg.chokepoint in blocked:
                    base = 100  # never traversed, but used for impact math
                risk += base
            else:
                risk += 5.0  # open-sea baseline risk
        return round(min(100.0, max(0.0, risk)), 1)

    # ── Impact helpers ─────────────────────────────────────────────────────

    def _voyage_days(self, total_km: float) -> float:
        """Average container-ship speed ≈ 450 km/day (incl. port dwell)."""
        return round(total_km / 450.0, 1)

    def _voyage_cost(self, total_km: float, cargo_value: float) -> float:
        """Rough cost: fuel+charter $1.75/km + 0.4% of cargo value at risk."""
        return round(total_km * 1.75 + cargo_value * 0.004, 0)

    def simulate(
        self,
        origin: str,
        destination: str,
        blocked_chokepoints: Optional[List[str]] = None,
        event_type: str = "war_conflict",
        cargo_value: float = 1_000_000.0,
    ) -> Dict[str, Any]:
        """Simulate the journey, apply blockages, return baseline + diversion."""
        if origin not in PORT_COORDS or destination not in PORT_COORDS:
            raise ValueError(f"Unknown port. Valid ports: {sorted(PORT_COORDS)}")
        if origin == destination:
            raise ValueError("Origin and destination must be different ports")
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event type. Valid: {sorted(EVENT_TYPES)}")

        blocked = [b for b in (blocked_chokepoints or []) if b in CHOKEPOINTS]

        # Baseline = shortest path with NO blockages.
        baseline = self.shortest_path(origin, destination, None)

        # Which chokepoints on the baseline path are now blocked?
        used_chokepoints = [s.chokepoint for s in baseline.path if s.chokepoint]
        hit = [cp for cp in blocked if cp in used_chokepoints]

        status = "clear"
        diverted: Optional[RouteResult] = None
        if hit:
            # Diverted = shortest path avoiding blocked chokepoints.
            diverted = self.shortest_path(origin, destination, blocked)
            if diverted.empty:
                status = "no_alternative"
            else:
                status = "diverted"

        if diverted is None:
            impact = {
                "extra_km": 0.0,
                "extra_days": 0.0,
                "extra_cost": 0.0,
                "risk_baseline": baseline.total_risk,
                "risk_diverted": baseline.total_risk,
            }
        else:
            impact = {
                "extra_km": round(max(0.0, diverted.total_km - baseline.total_km), 1),
                "extra_days": round(
                    max(0.0, self._voyage_days(diverted.total_km) - self._voyage_days(baseline.total_km)), 1
                ),
                "extra_cost": round(
                    max(0.0, self._voyage_cost(diverted.total_km, cargo_value) - self._voyage_cost(baseline.total_km, cargo_value)), 0
                ),
                "risk_baseline": baseline.total_risk,
                "risk_diverted": diverted.total_risk,
            }

        blocked_meta = [
            {"id": cp, **CHOKEPOINTS[cp]}
            for cp in blocked
        ]

        return {
            "simulation_id": uuid.uuid4().hex[:12],
            "origin": {"id": origin, **PORT_COORDS[origin]},
            "destination": {"id": destination, **PORT_COORDS[destination]},
            "event": {"id": event_type, **EVENT_TYPES[event_type]},
            "status": status,
            "blocked_chokepoints": blocked_meta,
            "impact": impact,
            "baseline": self._route_payload(baseline),
            "diverted": self._route_payload(diverted) if diverted is not None and not diverted.empty else None,
            "recommendation": self._recommendation(status, hit, impact),
        }

    def _route_payload(self, route: RouteResult) -> Dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in route.path],
            "port_ids": [s.from_port for s in route.path] + ([route.path[-1].to_port] if route.path else []),
            "total_km": round(route.total_km, 1),
            "days": self._voyage_days(route.total_km),
            "cost": self._voyage_cost(route.total_km, 1_000_000.0),
            "risk": route.total_risk,
            "chokepoints": [s.chokepoint for s in route.path if s.chokepoint],
        }

    def _recommendation(self, status: str, hit: List[str], impact: Dict[str, Any]) -> str:
        if status == "clear":
            return (
                "All sea and land corridors are open. The baseline route is the "
                "fastest and lowest-risk option — no diversion required."
            )
        if status == "no_alternative":
            return (
                "Blocked chokepoints sever every connection between these ports. "
                "Consider alternate origins/destinations, multimodal routing "
                "(rail/air bridge), or holding cargo until the lane reopens."
            )
        names = [CHOKEPOINTS[c]["name"] for c in hit]
        return (
            f"{', '.join(names)} {'is' if len(hit) == 1 else 'are'} disrupted. "
            f"Diverting adds {impact['extra_km']:,.0f} km "
            f"(~{impact['extra_days']} days, +${impact['extra_cost']:,.0f}). "
            "The recommended alternative route avoids the affected chokepoints."
        )
