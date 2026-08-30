"""Real-time weather services for supply-route monitoring.

Provider priority mirrors the news stack: Open-Meteo (free, no API key) when
reachable, else deterministic simulated conditions so the route-weather UI
never goes empty — see ``open_meteo.py``. Risk scoring and route aggregation
live in ``risk.py``.
"""
