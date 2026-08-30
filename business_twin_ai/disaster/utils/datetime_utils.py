"""Datetime helpers for the disaster validation layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def parse_datetime(value: Any) -> Optional[datetime]:
    """Normalise a datetime or ISO-8601 string into a tz-aware UTC datetime.

    Returns None for unparseable values.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None
