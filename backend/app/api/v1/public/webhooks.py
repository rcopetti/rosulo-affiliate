from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/tenant")
async def tenant_webhook(payload: dict):
    raise HTTPException(
        status_code=410,
        detail="Incoming payment-record webhooks are retired; send a confirmed sale event",
    )


@router.post("/paypal")
async def paypal_webhook(payload: dict):
    raise HTTPException(status_code=410, detail="PayPal payout webhooks are disabled")
