"""Shared primitives for the validation pipeline stages.

Each stage is an independent unit: it receives a :class:`StageContext`, performs
one focused check, and returns a small result object. Stages never call each
other — the pipeline orchestrates them in order and stores every result in
``context.results[stage.name]``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.config import config as default_config

logger = logging.getLogger("business_twin_ai.disaster.validation")


@runtime_checkable
class ValidationStage(Protocol):
    """A single, independent validation stage."""

    name: str

    async def run(self, context: "StageContext") -> Any:
        """Execute the stage and return its result object."""
        ...


@dataclass
class StageContext:
    """Everything a stage may need, plus accumulated stage results."""

    payload: Dict[str, Any]
    db: Optional[AsyncSession] = None
    config: ValidationConfig = field(default_factory=lambda: default_config)
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    results: Dict[str, Any] = field(default_factory=dict)
    stage_times: Dict[str, float] = field(default_factory=dict)
    notes: list = field(default_factory=list)


def log_stage(stage_name: str, message: str, duration_ms: float, **extra: Any) -> None:
    """Structured log line for a validation step (spec §12)."""
    extras = ", ".join(f"{k}={v}" for k, v in sorted(extra.items()))
    suffix = f" ({extras})" if extras else ""
    logger.info("[validation] %-12s %s in %.2fms%s", stage_name, message, duration_ms, suffix)


class TimedStageMixin:
    """Mixin that wraps ``run`` with execution-time measurement + logging."""

    async def timed_run(self, context: StageContext) -> Any:
        start = time.perf_counter()
        result = await self.run(context)  # type: ignore[misc]
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        context.stage_times[self.name] = elapsed_ms  # type: ignore[attr-defined]
        log_stage(self.name, "completed", elapsed_ms, **self._log_fields(result))  # type: ignore[attr-defined]
        return result

    def _log_fields(self, result: Any) -> Dict[str, Any]:
        """Derive a few scalar fields for the log line from the result."""
        if result is None:
            return {}
        out: Dict[str, Any] = {}
        for key in ("valid", "score", "suspicious", "duplicate", "confidence_score"):
            if hasattr(result, key):
                out[key] = getattr(result, key)
        return out
