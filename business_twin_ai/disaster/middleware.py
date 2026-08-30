"""ValidationMiddleware (spec §11).

Every report-creation API automatically flows through
``ValidationMiddleware → ValidationService → Store``. Controllers contain no
validation logic — the middleware intercepts matching requests, runs the full
pipeline and returns the validated response directly.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Set

from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from business_twin_ai.database import async_session_factory
from business_twin_ai.disaster.engines.service import ValidationService
from business_twin_ai.disaster.schemas.schemas import DisasterReportCreate

logger = logging.getLogger("business_twin_ai.disaster.validation")


class ValidationMiddleware(BaseHTTPMiddleware):
    """Intercepts report-creation requests and funnels them through validation.

    Configure which paths are treated as report-creation endpoints via
    ``create_paths``. Everything else passes straight through untouched, so
    existing endpoints are never affected.
    """

    def __init__(
        self,
        app,
        create_paths: Set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.create_paths = create_paths or {"/api/v1/disaster/reports"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method != "POST" or request.url.path not in self.create_paths:
            return await call_next(request)

        try:
            body = await request.body()
            payload: Dict = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)

        # Mirror the route handler's schema validation — the middleware runs
        # before FastAPI's request validation, so malformed payloads must be
        # rejected here.
        try:
            payload = DisasterReportCreate(**payload).model_dump(exclude_none=True)
        except ValidationError as exc:
            return JSONResponse(
                {"detail": "Invalid report payload", "errors": exc.errors()},
                status_code=422,
            )

        try:
            async with async_session_factory() as session:
                service = ValidationService(session)
                outcome = await service.submit_report(payload)
                # Always commit: trust-score updates for rejected reports must
                # persist too (spec §8 — updated after every report). Rejected
                # reports never add a DisasterReport row, so this is safe.
                await session.commit()
        except Exception as exc:  # noqa: BLE001 — surface as 500, never crash the app
            logger.exception("report validation failed: %s", exc)
            return JSONResponse({"detail": "Report validation failed"}, status_code=500)

        return JSONResponse(
            content={"report_id": outcome.report_id, "validation": outcome.validation},
            status_code=outcome.status_code,
        )
