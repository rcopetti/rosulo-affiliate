from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.db.dependencies import get_db
from app.db.models import Tenant
from app.services import payment_record as payment_service
from app.services import commission as commission_service
from app.services import event as event_service

router = APIRouter()


@router.post("/tenant")
async def tenant_webhook(
    payload: dict,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    record = await payment_service.upsert_payment_record(
        db,
        tenant,
        payload.get("payment_record_id"),
        payload.get("customer_id"),
        float(payload.get("amount", 0)),
        payload.get("currency", "USD"),
        int(payload.get("sequence_number", 1)),
        payload.get("status", "paid"),
    )
    await commission_service.mark_available_commissions(db)
    return {"status": "ok", "payment_record_id": record.tenant_payment_id}


@router.post("/paypal")
async def paypal_webhook(payload: dict):
    return {"status": "ok"}
