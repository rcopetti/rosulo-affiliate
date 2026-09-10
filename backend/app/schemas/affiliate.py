import uuid

from pydantic import BaseModel, ConfigDict, Field


class AffiliateCreate(BaseModel):
    email: str
    password: str
    name: str
    country: str
    state: str | None = None
    tax_id: str | None = None
    tax_status: str = "us_person"
    tax_form_type: str | None = None
    paypal_email: str | None = None
    backup_withholding_required: bool = False


class AffiliateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID = Field(validation_alias="affiliate_account_id")
    kyc_approved_for_payout: bool
