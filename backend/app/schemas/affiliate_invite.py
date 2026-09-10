import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


class AffiliateInviteCreate(BaseModel):
    email: EmailStr
    contract_terms: list[dict[str, Any]] | None = None


class AffiliateInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    token: str
    contract_terms: list[dict[str, Any]]
    status: str
    expires_at: datetime.datetime | None = None
    created_at: datetime.datetime


class AffiliateInviteAccept(BaseModel):
    token: str
    email: EmailStr | None = None
    password: str | None = None
    name: str | None = None
    country: str | None = None
    state: str | None = None
    tax_status: str = "us_person"
    tax_form_type: str | None = None
    paypal_email: str | None = None


class PendingInviteOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    token: str
    expires_at: datetime.datetime | None = None
