import uuid

from pydantic import BaseModel, ConfigDict


class TenantCreate(BaseModel):
    name: str


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
