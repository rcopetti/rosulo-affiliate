"""Payout payment-notification delivery lifecycle.

``confirm_payout_payment`` creates one ``pending`` PayoutNotification row in
the payment transaction. Delivery happens only after that commit — from a
FastAPI BackgroundTasks job on the confirming request, or from the daily
payout-maintenance task recovering work a crashed process left behind.

Claim protocol (two workers must never double-send):

1. A conditional UPDATE flips a *deliverable* row — ``pending``, or
   ``sending`` whose lease has expired — to ``sending`` with a fresh
   10-minute lease and an incremented ``attempt_count``, then COMMITS before
   the provider call. Racing workers get rowcount 1 and 0.
2. After the provider accepts the send the row goes to ``sent``/``sent_at``;
   on error it goes to ``failed`` with ``last_error``. Both branches clear
   the lease. A crash between claim and outcome leaves an expirable lease
   the next maintenance run re-claims; the resulting duplicate email is
   acceptable and harmless.

``updated_at`` is set explicitly on every UPDATE: the ORM ``onupdate``
callback does not fire for Core updates.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Affiliate, Payout, PayoutNotification
from app.db.session import async_session
from app.services.email import send_payout_paid_email

logger = logging.getLogger(__name__)

NOTIFICATION_LEASE = timedelta(minutes=10)
MAX_ERROR_LENGTH = 1000
BATCH_LIMIT = 200


def _deliverable(now: datetime):
    return or_(
        PayoutNotification.status == "pending",
        and_(
            PayoutNotification.status == "sending",
            PayoutNotification.lease_expires_at <= now,
        ),
    )


async def _claim_notification(db: AsyncSession, payout_id: uuid.UUID) -> bool:
    """Atomically claim the payout's notification for delivery."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(PayoutNotification)
        .where(
            PayoutNotification.payout_id == payout_id,
            _deliverable(now),
        )
        .values(
            status="sending",
            attempt_count=PayoutNotification.attempt_count + 1,
            last_attempt_at=now,
            lease_expires_at=now + NOTIFICATION_LEASE,
            updated_at=now,
        )
    )
    # Commit BEFORE the provider call: a crash mid-send must leave a
    # visible, expirable lease rather than a row that looks untouched.
    await db.commit()
    return result.rowcount == 1


async def deliver_payout_notification(
    db: AsyncSession, payout_id: uuid.UUID
) -> str | None:
    """Claim the payout's notification and attempt one delivery.

    Returns ``"sent"``/``"failed"`` when this call owned the delivery, or
    ``None`` when another worker holds the lease or the row is already in a
    terminal state. Send failures only touch the notification row — payout
    and payment state are never reverted.
    """
    if not await _claim_notification(db, payout_id):
        return None

    result = await db.execute(
        select(Payout)
        .where(Payout.id == payout_id)
        .options(
            selectinload(Payout.affiliate).selectinload(Affiliate.account),
            selectinload(Payout.payout_payment),
        )
    )
    payout = result.scalar_one()
    payment = payout.payout_payment
    now = datetime.now(timezone.utc)
    try:
        if payment is None:
            raise RuntimeError("payout has no recorded payment")
        await send_payout_paid_email(
            to=payout.affiliate.account.email,
            affiliate_name=payout.affiliate.account.name,
            payout=payout,
            payment=payment,
        )
    except Exception as exc:
        logger.exception(
            "payout notification send failed payout_id=%s", payout_id
        )
        await db.execute(
            update(PayoutNotification)
            .where(PayoutNotification.payout_id == payout_id)
            .values(
                status="failed",
                last_error=f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH],
                lease_expires_at=None,
                updated_at=now,
            )
        )
        await db.commit()
        return "failed"

    await db.execute(
        update(PayoutNotification)
        .where(PayoutNotification.payout_id == payout_id)
        .values(
            status="sent",
            sent_at=now,
            last_error=None,
            lease_expires_at=None,
            updated_at=now,
        )
    )
    await db.commit()
    return "sent"


async def send_payout_notification(payout_id: uuid.UUID) -> None:
    """BackgroundTasks entrypoint: opens a fresh session per send.

    The request session is closed by the time background tasks run, so a
    dedicated session is required. Delivery errors are persisted on the
    notification row by ``deliver_payout_notification``; anything else
    (database down, claim race fallout) is logged and left for the daily
    job's expired-lease recovery.
    """
    try:
        async with async_session() as db:
            await deliver_payout_notification(db, payout_id)
    except Exception:
        logger.exception(
            "payout notification task failed payout_id=%s", payout_id
        )


async def process_due_notifications(
    db: AsyncSession, *, limit: int = BATCH_LIMIT
) -> dict:
    """Claim and deliver every due notification on the given session.

    Due means ``pending`` or ``sending`` with an expired lease. The atomic
    claim inside ``deliver_payout_notification`` keeps a web worker mid-send
    from being double-delivered by the daily task.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PayoutNotification.payout_id)
        .where(_deliverable(now))
        .order_by(PayoutNotification.created_at)
        .limit(limit)
    )
    payout_ids = list(result.scalars().all())
    summary = {"claimed": 0, "sent": 0, "failed": 0}
    for payout_id in payout_ids:
        outcome = await deliver_payout_notification(db, payout_id)
        if outcome is None:
            continue
        summary["claimed"] += 1
        summary[outcome] += 1
    return summary
