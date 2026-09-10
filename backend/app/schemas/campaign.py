import uuid

from pydantic import BaseModel, ConfigDict


class CampaignBase(BaseModel):
    name: str
    landing_url: str
    active: bool = True


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: str | None = None
    landing_url: str | None = None
    active: bool | None = None


class CampaignOut(CampaignBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    tracking_code: str
