import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class TenantCreate(BaseModel):
    name: str


class TenantUpdate(BaseModel):
    name: str | None = None
    allowed_domains: list[str] | None = None


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    allowed_domains: list[str]
