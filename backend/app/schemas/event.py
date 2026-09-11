import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EventCreate(BaseModel):
    event_id: str
    type: str = Field(..., pattern="^(click|lead|sale)$")
    campaign_id: str | None = None
    tracking_code: str | None = None
    click_id: str | None = None
    lead_id: str | None = None
    customer_id: str | None = None
    customer_email: str | None = None
    amount: float = 0.0
    currency: str = "USD"
    payment_sequence: int = 1
    good_date: date | None = None
    payment_record_id: str | None = None
    referer: str | None = None
    page_url: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    occurred_at: datetime | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: str
    type: str
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    customer_id: str | None = None
    amount: float
    currency: str
    payment_sequence: int
    good_date: date | None = None
    payment_record_id: str | None = None
    referer: str | None = None
    page_url: str | None = None
    occurred_at: datetime | None = None
