import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventCreate(BaseModel):
    event_id: str
    type: str = Field(..., pattern="^(click|lead|sale)$")
    campaign_id: str | None = None
    tracking_code: str | None = None
    click_id: str | None = None
    lead_id: str | None = None
    customer_id: str | None = None
    customer_email: str | None = None
    amount: Decimal = Decimal("0.00")
    currency: str = Field("USD", pattern="^[A-Za-z]{3}$")
    payment_sequence: int = 0
    good_date: date | None = None
    payment_record_id: str | None = None
    referer: str | None = None
    page_url: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    occurred_at: datetime | None = None

    @field_validator("payment_record_id")
    @classmethod
    def strip_payment_record_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip()

    @model_validator(mode="after")
    def sale_requires_good_date_and_payment_record_id(self):
        if self.type == "sale":
            if self.good_date is None:
                raise ValueError("good_date is required for sale events")
            if not self.payment_record_id or not self.payment_record_id.strip():
                raise ValueError("payment_record_id is required for sale events")
        return self


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: str
    type: str
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    affiliate_id: uuid.UUID | None = None
    customer_id: str | None = None
    amount: float
    currency: str
    commission_status: str | None = None
    payment_sequence: int
    good_date: date | None = None
    payment_record_id: str | None = None
    referer: str | None = None
    page_url: str | None = None
    occurred_at: datetime | None = None


class PaginatedEvents(BaseModel):
    items: list[EventOut]
    total: int
    skip: int
    limit: int
