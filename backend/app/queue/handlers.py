import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Commission, Payout
from app.integrations import paypal


async def handle_payout(db: AsyncSession, payout_id: str):
    result = await db.execute(select(Payout).where(Payout.id == uuid.UUID(payout_id)))
    payout = result.scalar_one_or_none()
    if not payout or payout.status in ("paid", "failed"):
        return

    payout.status = "processing"
    await db.commit()

    try:
        batch_id = await paypal.send_payout(
            payout.net_paid, payout.currency, payout.affiliate.paypal_email
        )
        payout.paypal_batch_id = batch_id
        payout.status = "paid"
        payout.paid_at = __import__("datetime").datetime.utcnow()
        result = await db.execute(
            select(Commission).where(
                Commission.id.in_([pc.commission_id for pc in payout.payout_commissions])
            )
        )
        for c in result.scalars().all():
            c.status = "paid"
    except Exception:
        payout.status = "failed"
        result = await db.execute(
            select(Commission).where(
                Commission.id.in_([pc.commission_id for pc in payout.payout_commissions])
            )
        )
        for c in result.scalars().all():
            c.status = "available"
    await db.commit()
