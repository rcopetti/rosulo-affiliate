import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PayoutRequest(BaseModel):
    currency: str = Field(..., pattern="^[A-Za-z]{3}$")


class PayoutPaymentConfirmation(BaseModel):
    payment_method: str = Field(..., min_length=1, max_length=50)
    transfer_reference: str = Field(..., min_length=1, max_length=255)

    @field_validator("payment_method", "transfer_reference")
    @classmethod
    def strip_required_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value


class PayoutPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    payout_id: uuid.UUID
    amount: float
    currency: str
    payment_method: str
    transfer_reference: str
    paid_at: datetime
    recorded_by_tenant_user_id: uuid.UUID


class PayoutTransitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sequence: int
    from_status: str | None
    to_status: str
    actor_tenant_user_id: uuid.UUID | None
    reason: str | None
    created_at: datetime


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
    payment_record: PayoutPaymentOut | None = None
    transitions: list[PayoutTransitionOut] = Field(default_factory=list)
