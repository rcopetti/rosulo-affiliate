import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class AffiliateAccountBase(BaseModel):
    email: EmailStr
    name: str
    country: str
    state: str | None = None
    postal_code: str | None = None
    tax_id: str | None = None
    tax_status: str = "us_person"
    tax_form_type: str | None = None
    paypal_email: str | None = None
    backup_withholding_required: bool = False


class AffiliateAccountCreate(AffiliateAccountBase):
    password: str


class AffiliateAccountUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    state: str | None = None
    postal_code: str | None = None
    tax_id: str | None = None
    tax_status: str | None = None
    tax_form_type: str | None = None
    paypal_email: str | None = None
    backup_withholding_required: bool | None = None


class AffiliateAccountOut(AffiliateAccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
