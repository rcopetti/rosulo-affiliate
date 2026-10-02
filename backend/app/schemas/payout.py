import uuid
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import AliasPath, BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


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


class PayoutAffiliateOut(BaseModel):
    """Payee identity resolved from the affiliate's account record."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str
    paypal_email: str | None = None


class PayoutCommissionDetailOut(BaseModel):
    """One commission line of a payout, enriched with its source sale Event.

    Validated from a ``PayoutCommission`` link row; every field traverses the
    linked ``Commission`` (and its source ``Event`` for the sale timestamp,
    good date, and payment sequence) so merchants can reconcile each line
    back to the sale that earned it.
    """

    model_config = ConfigDict(from_attributes=True)

    commission_id: uuid.UUID = Field(validation_alias=AliasPath("commission", "id"))
    event_id: uuid.UUID = Field(validation_alias=AliasPath("commission", "event_id"))
    occurred_at: datetime | None = Field(
        default=None, validation_alias=AliasPath("commission", "event", "occurred_at")
    )
    good_date: date | None = Field(
        default=None, validation_alias=AliasPath("commission", "event", "good_date")
    )
    payment_sequence: int | None = Field(
        default=None, validation_alias=AliasPath("commission", "event", "payment_sequence")
    )
    gross_amount: float = Field(validation_alias=AliasPath("commission", "gross_amount"))
    withholding_amount: float = Field(
        validation_alias=AliasPath("commission", "withholding_amount")
    )
    net_amount: float = Field(validation_alias=AliasPath("commission", "net_amount"))
    currency: str = Field(validation_alias=AliasPath("commission", "currency"))
    campaign_id: uuid.UUID | None = Field(
        default=None, validation_alias=AliasPath("commission", "campaign_id")
    )


PayoutStatus = Literal["pending_approval", "approved", "rejected", "paid"]


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
    status: PayoutStatus
    requested_at: datetime
    approved_at: datetime | None = None
    paid_at: datetime | None = None
    affiliate: PayoutAffiliateOut = Field(
        validation_alias=AliasPath("affiliate", "account")
    )
    payout_commissions: list[PayoutCommissionDetailOut] = Field(default_factory=list)
    payout_payment: PayoutPaymentOut | None = None
    transitions: list[PayoutTransitionOut] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sort_commission_lines(self) -> "PayoutOut":
        # Deterministic merchant review order: by source-sale time, then ID.
        self.payout_commissions.sort(
            key=lambda line: (
                line.occurred_at is None,
                line.occurred_at,
                line.commission_id,
            )
        )
        return self

    @computed_field
    @property
    def commission_count(self) -> int:
        return len(self.payout_commissions)

    @computed_field
    @property
    def earliest_sale_at(self) -> datetime | None:
        times = [
            line.occurred_at
            for line in self.payout_commissions
            if line.occurred_at is not None
        ]
        return min(times, default=None)

    @computed_field
    @property
    def latest_sale_at(self) -> datetime | None:
        times = [
            line.occurred_at
            for line in self.payout_commissions
            if line.occurred_at is not None
        ]
        return max(times, default=None)
