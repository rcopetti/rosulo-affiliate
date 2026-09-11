from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Commission, Event, PaymentRecord, Tenant


async def upsert_payment_record(
    db: AsyncSession,
    tenant: Tenant,
    tenant_payment_id: str,
    customer_id: str,
    amount: float,
    currency: str,
    sequence_number: int,
    status: str,
    paid_at: datetime | None = None,
) -> PaymentRecord:
    result = await db.execute(
        select(PaymentRecord).where(
            PaymentRecord.tenant_id == tenant.id,
            PaymentRecord.tenant_payment_id == tenant_payment_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        record = PaymentRecord(
            tenant_id=tenant.id,
            tenant_payment_id=tenant_payment_id,
            customer_id=customer_id,
            amount=amount,
            currency=currency,
            paid_at=paid_at or datetime.utcnow(),
            sequence_number=sequence_number,
            status=status,
        )
        db.add(record)
    else:
        record.status = status
    await db.commit()
    await db.refresh(record)
    return record
