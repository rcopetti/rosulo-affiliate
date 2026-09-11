import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class TenantUserBase(BaseModel):
    email: EmailStr
    name: str | None = None
    role: str = "admin"


class TenantUserCreate(TenantUserBase):
    password: str


class TenantUserLogin(BaseModel):
    email: EmailStr
    password: str


class TenantUserOut(TenantUserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
