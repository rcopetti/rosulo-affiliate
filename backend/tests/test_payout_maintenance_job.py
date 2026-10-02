"""Tests for the one-shot payout maintenance job (ECS Fargate scheduled task).

The job runs outside the FastAPI app: it opens a single database session,
promotes due commissions via ``mature_due_commissions``, logs a run summary,
and propagates failures so the container exits non-zero and the failed run is
visible in ECS stopped-task / CloudWatch logs.
"""

import asyncio
import logging
import uuid
from datetime import datetime

import pytest

from app.jobs import payout_maintenance


class _FakeSession:
    """Minimal async context manager standing in for ``AsyncSession``.

    The job only needs ``async with db_factory() as db``; the service call is
    monkeypatched, so no real database work happens here.
    """

    def __init__(self):
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True
        return False


@pytest.mark.asyncio
async def test_run_maturity_job_logs_and_returns_summary(monkeypatch, caplog):
    """A successful run returns a summary with the promoted count and run ID,
    passes the opened session to the service, and closes the session."""
    seen_sessions = []

    async def fake_mature(db, now_utc=None):
        seen_sessions.append(db)
        return 3

    monkeypatch.setattr(payout_maintenance, "mature_due_commissions", fake_mature)
    session = _FakeSession()

    with caplog.at_level(logging.INFO, logger="app.jobs.payout_maintenance"):
        summary = await payout_maintenance.run_maturity_job(lambda: session)

    assert summary["promoted_count"] == 3
    assert seen_sessions == [session]
    assert session.closed is True

    # Run ID is a valid UUID and the UTC timestamps parse.
    uuid.UUID(summary["run_id"])
    started_at = datetime.fromisoformat(summary["started_at"])
    ended_at = datetime.fromisoformat(summary["ended_at"])
    assert started_at.tzinfo is not None
    assert ended_at >= started_at

    # The summary is logged so the run is auditable in CloudWatch.
    assert any("promoted_count" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_run_maturity_job_propagates_failure(monkeypatch, caplog):
    """A service failure propagates out of run_maturity_job so the ECS task
    exits non-zero; the session context still closes (rolling back any open
    transaction) and a failure record identifying the run is logged."""

    async def fake_mature(db, now_utc=None):
        raise RuntimeError("database connection lost")

    monkeypatch.setattr(payout_maintenance, "mature_due_commissions", fake_mature)
    session = _FakeSession()

    with caplog.at_level(logging.INFO, logger="app.jobs.payout_maintenance"):
        with pytest.raises(RuntimeError, match="database connection lost"):
            await payout_maintenance.run_maturity_job(lambda: session)

    assert session.closed is True

    # The failed run is logged with its run_id so it is auditable in
    # CloudWatch alongside the non-zero container exit.
    failure_records = [
        record
        for record in caplog.records
        if "payout maintenance run failed" in record.getMessage()
    ]
    assert failure_records, "expected a failure log record for the run"
    assert any("run_id=" in record.getMessage() for record in failure_records)
    assert any(record.levelno >= logging.ERROR for record in failure_records)


@pytest.mark.asyncio
async def test_run_maturity_job_times_out_and_closes_session(monkeypatch):
    """When the service call exceeds JOB_TIMEOUT_SECONDS, the asyncio.timeout
    expiry propagates out of run_maturity_job (non-zero container exit) and
    the session context still closes."""

    async def fake_mature(db, now_utc=None):
        await asyncio.sleep(1)
        return 0

    monkeypatch.setattr(payout_maintenance, "mature_due_commissions", fake_mature)
    monkeypatch.setattr(payout_maintenance, "JOB_TIMEOUT_SECONDS", 0.05)
    session = _FakeSession()

    with pytest.raises(asyncio.TimeoutError):
        await payout_maintenance.run_maturity_job(lambda: session)

    assert session.closed is True


def test_module_exposes_container_entrypoints():
    """The module must expose ``main`` (for ``python -m
    app.jobs.payout_maintenance``) and ``run_maturity_job`` without importing
    FastAPI request handlers."""
    import app.jobs.payout_maintenance as module

    assert callable(module.main)
    assert callable(module.run_maturity_job)
    assert module.main_async.__name__ == "main_async"
