import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.services.tax_profile import TaxEntityType, TaxStatus


class AffiliateDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_type: str
    approved: bool
    created_at: datetime.datetime


class AffiliateAccountBase(BaseModel):
    email: EmailStr
    name: str
    country: str
    state: str | None = None
    postal_code: str | None = None
    tax_id: str | None = None
    tax_status: TaxStatus = "us_person"
    tax_entity_type: TaxEntityType = "individual"
    business_name: str | None = None
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
    tax_status: TaxStatus | None = None
    tax_entity_type: TaxEntityType | None = None
    business_name: str | None = None
    tax_form_type: str | None = None
    paypal_email: str | None = None
    backup_withholding_required: bool | None = None


class AffiliateAccountOut(AffiliateAccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    documents: list[AffiliateDocumentOut] = []
