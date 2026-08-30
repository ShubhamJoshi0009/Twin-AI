"""Reporter trust score engine (spec §8)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.config import config as default_config
from business_twin_ai.disaster.models import ReporterProfile

logger = logging.getLogger("business_twin_ai.disaster.validation")


class ReporterTrustService:
    """Maintains per-reporter trust (0-100) and verification history.

    Trust is adjusted after every report (spec §8):
        accepted   +2
        rejected  -10
        duplicate  -3
        suspicious -5
        false      -15
    """

    def __init__(
        self,
        db: AsyncSession,
        config: ValidationConfig = default_config,
    ) -> None:
        self.db = db
        self.config = config

    async def get(self, reporter_id: str) -> Optional[ReporterProfile]:
        result = await self.db.execute(
            select(ReporterProfile).where(ReporterProfile.reporter_id == reporter_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, reporter_id: str) -> ReporterProfile:
        profile = await self.get(reporter_id)
        if profile is None:
            profile = ReporterProfile(
                reporter_id=reporter_id,
                reporter_trust_score=self.config.TRUST_START,
                verification_history=[],
            )
            self.db.add(profile)
            await self.db.flush()
        return profile

    async def record_outcome(
        self,
        reporter_id: str,
        report_id: str,
        *,
        accepted: bool = False,
        rejected: bool = False,
        duplicate: bool = False,
        suspicious: bool = False,
        false_report: bool = False,
        notes: Optional[List[str]] = None,
    ) -> ReporterProfile:
        """Update trust + history after a report is processed."""
        profile = await self.get_or_create(reporter_id)
        delta = 0.0

        profile.total_reports += 1
        if accepted:
            profile.accepted_reports += 1
            delta += self.config.TRUST_ACCEPTED_DELTA
        if rejected:
            profile.rejected_reports += 1
            delta += self.config.TRUST_REJECTED_DELTA
        if duplicate:
            profile.duplicate_reports += 1
            delta += self.config.TRUST_DUPLICATE_DELTA
        if suspicious or false_report:
            profile.false_reports += 1
            delta += self.config.TRUST_SUSPICIOUS_DELTA
            if false_report:
                delta += self.config.TRUST_FALSE_REPORT_DELTA

        new_score = max(
            self.config.TRUST_MIN,
            min(self.config.TRUST_MAX, profile.reporter_trust_score + delta),
        )
        profile.reporter_trust_score = round(new_score, 2)
        profile.last_report_at = datetime.now(timezone.utc)
        history = profile.verification_history or []
        history.append(
            {
                "report_id": report_id,
                "accepted": accepted,
                "rejected": rejected,
                "duplicate": duplicate,
                "suspicious": suspicious,
                "false_report": false_report,
                "notes": notes or [],
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        profile.verification_history = history[-50:]  # keep last 50 entries
        await self.db.flush()
        logger.info(
            "[trust] reporter=%s trust=%.2f (delta=%.1f)",
            reporter_id,
            profile.reporter_trust_score,
            delta,
        )
        return profile
