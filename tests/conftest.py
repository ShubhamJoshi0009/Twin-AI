"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
import pytest_asyncio  # noqa: F401 — ensures the asyncio plugin is registered

# Some suites exercise the seed API, which is disabled by default in
# production. Set it before any test module imports the app (the Settings
# singleton is frozen at first import).
os.environ.setdefault("ENABLE_SEED_API", "true")

# Route-weather tests must be deterministic and offline-safe: force the
# simulated weather provider for the whole process (live Open-Meteo would
# otherwise be frozen into the Settings singleton by the first import).
os.environ.setdefault("WEATHER_FORCE_SIMULATED", "true")

# The Settings singleton + SQLAlchemy engine are created at first import of
# business_twin_ai, so tests must decide the DB *before* any test module
# imports the package. Without this, the alphabetically-first test module
# freezes the engine to the Postgres default and every subsequent suite fails
# with asyncpg errors. A shared SQLite DB keeps the whole suite deterministic
# in CI (where no .env provides DATABASE_URL).
#
# Note: because of this, all test files share one SQLite file (per-file
# `os.environ.setdefault("DATABASE_URL", …)` lines become no-ops). Each suite
# is self-contained in the data it creates and asserts on, so this is safe;
# if suites grow more interdependent, switch database.py to a lazy engine.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_suite_runtime.db")

# Report engines write PDFs to REPORT_OUTPUT_DIR — point it at a throwaway temp
# dir so the test suite never leaves stray artifacts in the repo root.
os.environ.setdefault("REPORT_OUTPUT_DIR", tempfile.mkdtemp(prefix="bta_test_reports_"))


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
