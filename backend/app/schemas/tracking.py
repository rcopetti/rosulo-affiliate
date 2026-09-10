from pydantic import BaseModel, Field


class TrackClick(BaseModel):
    tracking_code: str = Field(..., min_length=1)
    customer_id: str | None = None
    referer: str | None = None
    page_url: str | None = None
    event_id: str | None = None


class TrackClickOut(BaseModel):
    click_id: str
    campaign_id: str
