import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PayoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(..., pattern="^[A-Za-z]{3}$")
    commission_ids: list[uuid.UUID] | None = None

    @field_validator("commission_ids")
    @classmethod
    def validate_commission_ids(
        cls, value: list[uuid.UUID] | None
    ) -> list[uuid.UUID] | None:
        if value is not None and (not value or len(value) != len(set(value))):
            raise ValueError("commission_ids must contain unique commission IDs")
        return value


class PayoutPaymentConfirmation(BaseModel):
    # extra="forbid" keeps amount/currency/method server-derived: the client
    # only reports when the PayPal transfer actually completed and under which
    # reference.
    model_config = ConfigDict(extra="forbid")

    paid_at: datetime
    transfer_reference: str = Field(..., min_length=1, max_length=255)

    @field_validator("paid_at")
    @classmethod
    def validate_paid_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paid_at must include a timezone offset")
        if value > datetime.now(timezone.utc):
            raise ValueError("paid_at must not be in the future")
        return value

    @field_validator("transfer_reference")
    @classmethod
    def strip_transfer_reference(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("transfer_reference must not be blank")
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
    payout_payment: PayoutPaymentOut | None = None
    transitions: list[PayoutTransitionOut] = Field(default_factory=list)
