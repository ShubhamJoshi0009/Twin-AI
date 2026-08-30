"""Map warning state updater (spec §10)."""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Tuple

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.config import config as default_config

logger = logging.getLogger("business_twin_ai.disaster.validation")

# In-memory TTL cache for frequently-read cluster warning state.
_cache: Dict[str, Tuple[float, object]] = {}


class MapWarningStateUpdater:
    """Computes and caches the disaster-map warning level per cluster.

    Rules (configurable via :class:`ValidationConfig`):
        RED    severity > 8 AND reports > 20
        ORANGE severity >= 7 AND reports >= 10
        YELLOW severity >= 4 AND reports >= 3
        GREEN  otherwise (severity < 3 and reports < 3)
    """

    def __init__(self, config: ValidationConfig = default_config) -> None:
        self.config = config

    def compute_warning_level(self, average_severity: float, report_count: int) -> str:
        """Map an (average_severity, report_count) pair to GREEN/YELLOW/ORANGE/RED."""
        cfg = self.config
        if average_severity > cfg.WARN_RED_SEVERITY and report_count > cfg.WARN_RED_REPORTS:
            return "RED"
        if average_severity >= cfg.WARN_ORANGE_SEVERITY and report_count >= cfg.WARN_ORANGE_REPORTS:
            return "ORANGE"
        if average_severity >= cfg.WARN_YELLOW_SEVERITY and report_count >= cfg.WARN_YELLOW_REPORTS:
            return "YELLOW"
        return "GREEN"

    # ── Cache helpers (frequently accessed cluster info, spec §16) ─────────
    @staticmethod
    def cache_get(key: str) -> object | None:
        """Return a cached value if fresh, else None."""
        entry = _cache.get(key)
        if entry is None:
            return None
        cached_at, value = entry
        ttl = default_config.WARNING_CACHE_TTL_SECONDS
        if time.monotonic() - cached_at > ttl:
            _cache.pop(key, None)
            return None
        return value

    @staticmethod
    def cache_put(key: str, value: object) -> None:
        """Store a value in the warning cache."""
        _cache[key] = (time.monotonic(), value)

    @staticmethod
    def cache_invalidate(keys: List[str] | None = None) -> None:
        """Drop cache entries (after writes). None clears everything."""
        if keys is None:
            _cache.clear()
        else:
            for key in keys:
                _cache.pop(key, None)

    def update_warning_for(
        self,
        cluster_id: str,
        average_severity: float,
        report_count: int,
        disaster_type: str = "",
    ) -> str:
        """Compute the warning level, log it and cache it."""
        level = self.compute_warning_level(average_severity, report_count)
        logger.info(
            "[map] %s warning=%s (avg_severity=%.2f reports=%d type=%s)",
            cluster_id,
            level,
            average_severity,
            report_count,
            disaster_type,
        )
        self.cache_put(f"cluster:{cluster_id}", level)
        return level
