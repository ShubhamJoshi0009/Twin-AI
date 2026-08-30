"""Report metadata validation stage (spec §2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.utils.text import find_spam_words, repeated_char_ratio
from business_twin_ai.disaster.validation.base import StageContext, TimedStageMixin


@dataclass
class MetadataResult:
    """Result of metadata validation (score 0-100)."""

    metadata_score: float
    valid: bool = True
    warnings: List[str] = field(default_factory=list)


class MetadataValidationStage(TimedStageMixin):
    """Required fields, lengths, spam, empty/repeated text, timestamp sanity."""

    name = "metadata"

    async def run(self, context: StageContext) -> MetadataResult:
        cfg: ValidationConfig = context.config
        payload = context.payload
        score = 100.0
        warnings: List[str] = []

        # 1) Required fields present?
        for field_name in cfg.REQUIRED_FIELDS:
            value = payload.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                score -= cfg.PENALTY_MISSING_FIELD
                warnings.append(f"missing required field: {field_name}")

        title = (payload.get("title") or "").strip()
        description = (payload.get("description") or "").strip()

        # 2) Length validation.
        if title and len(title) < cfg.MIN_TITLE_LENGTH:
            score -= cfg.PENALTY_SHORT_TEXT
            warnings.append(f"title too short ({len(title)} chars)")
        if description and len(description) < cfg.MIN_DESCRIPTION_LENGTH:
            score -= cfg.PENALTY_SHORT_TEXT
            warnings.append(f"description too short ({len(description)} chars)")
        if description and len(description) > cfg.MAX_DESCRIPTION_LENGTH:
            score -= cfg.PENALTY_SHORT_TEXT
            warnings.append("description suspiciously long")

        # 3) Empty text / repeated characters / spam words.
        combined = f"{title} {description}"
        if not combined.strip():
            score -= cfg.PENALTY_MISSING_FIELD
            warnings.append("empty text")
        if repeated_char_ratio(combined) >= 0.5:
            score -= cfg.PENALTY_REPEATED_CHARS
            warnings.append("repeated characters detected")
        spam = find_spam_words(combined, cfg.SPAM_WORDS)
        if spam:
            score -= cfg.PENALTY_SPAM * len(spam)
            warnings.append(f"spam words: {', '.join(spam)}")

        # 4) Timestamp sanity: invalid or future timestamps.
        raw_ts = payload.get("timestamp")
        if raw_ts is None:
            score -= cfg.PENALTY_MISSING_FIELD
            warnings.append("missing timestamp (defaults to now)")
        else:
            ts = raw_ts
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    score -= cfg.PENALTY_INVALID_TIMESTAMP
                    warnings.append("invalid timestamp format")
                    ts = None
            if ts is not None:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                now = context.now
                if now.tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)
                if ts > now + timedelta(minutes=cfg.FUTURE_TOLERANCE_MINUTES):
                    score -= cfg.PENALTY_FUTURE_TIMESTAMP
                    warnings.append("timestamp is in the future")

        score = max(0.0, min(100.0, round(score, 2)))
        return MetadataResult(
            metadata_score=score,
            valid=score >= cfg.LOW_METADATA_SCORE,
            warnings=warnings,
        )
