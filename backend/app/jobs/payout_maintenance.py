"""One-shot payout maintenance job for the scheduled Fargate task.

Runs ``mature_due_commissions`` once in a single database session, then
delivers due payout notifications — ``pending`` rows plus ``sending`` rows
whose lease expired (a web worker that crashed mid-send) — logs a run
summary, and exits. Intended to be invoked by EventBridge Scheduler as an
ECS RunTask target — NOT inside the App Runner web server (App Runner can
run multiple replicas and restart independently, so an in-process scheduler
would duplicate or lose runs).

Container command: ``python -m app.jobs.payout_maintenance``

Failure semantics: any exception (including ``asyncio.timeout`` expiry)
propagates out of ``main()`` so the container exits non-zero; the stopped
task is then visible in ECS/CloudWatch and the next scheduled daily run
catches up.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from app.db.session import async_session
from app.services.commission import mature_due_commissions
from app.services.payout_notification import process_due_notifications

logger = logging.getLogger(__name__)

JOB_TIMEOUT_SECONDS = 600


async def run_maturity_job(db_factory=async_session) -> dict:
    """Promote due commissions once and return the run summary.

    ``db_factory`` is injectable so tests can supply a fake session and a
    monkeypatched service. The session context manager rolls back any open
    SQLAlchemy transaction when the job is cancelled or times out.
    """
    run_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    logger.info(
        "payout maintenance run started run_id=%s started_at=%s",
        run_id,
        started_at.isoformat(),
    )
    try:
        async with db_factory() as db:
            async with asyncio.timeout(JOB_TIMEOUT_SECONDS):
                promoted_count = await mature_due_commissions(db)
                notification_summary = await process_due_notifications(db)
    except BaseException:
        logger.exception("payout maintenance run failed run_id=%s", run_id)
        raise

    ended_at = datetime.now(timezone.utc)
    summary = {
        "run_id": str(run_id),
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "promoted_count": promoted_count,
        "notifications": notification_summary,
    }
    logger.info("payout maintenance run finished %s", summary)
    return summary


async def main_async() -> dict:
    return await run_maturity_job()


def main() -> None:
    # basicConfig so the run summary lands on container stdout (awslogs).
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
