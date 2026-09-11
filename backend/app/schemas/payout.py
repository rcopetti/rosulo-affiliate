import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PayoutRequest(BaseModel):
    pass


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    affiliate_id: uuid.UUID
    tenant_id: uuid.UUID
    requested_amount: float
    approved_amount: float
    withholding_total: float
    paypal_fees: float
    net_paid: float
    currency: str
    status: str
    requested_at: datetime
    approved_at: datetime | None = None
    paid_at: datetime | None = None


class PayoutAction(BaseModel):
    action: str
