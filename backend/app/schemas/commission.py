import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class CommissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    gross_amount: float
    withholding_amount: float
    net_amount: float
    currency: str
    status: str
    available_on: date | None = None
