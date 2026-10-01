import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AffiliateCreate(BaseModel):
    email: str
    password: str
    name: str
    country: str
    state: str | None = None
    postal_code: str | None = None
    tax_id: str | None = None
    tax_status: str = "us_person"
    tax_form_type: str | None = None
    paypal_email: str | None = None
    backup_withholding_required: bool = False


class DocumentReviewerOut(BaseModel):
    id: uuid.UUID
    name: str | None = None
    email: str


class DocumentReviewOut(BaseModel):
    status: str
    reviewed_at: datetime.datetime
    rejection_reason: str | None = None
    reviewer: DocumentReviewerOut


class AffiliateDocumentOut(BaseModel):
    id: uuid.UUID
    document_type: str
    content_type: str
    created_at: datetime.datetime
    status: str
    review_history: list[DocumentReviewOut]


class PayoutEligibilityOut(BaseModel):
    eligible: bool
    status: str
    reason: str | None = None


class AffiliateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID = Field(validation_alias="affiliate_account_id")
    email: str
    name: str
    country: str | None = None
    state: str | None = None
    postal_code: str | None = None
    paypal_email: str | None = None
    tax_status: str | None = None
    tax_entity_type: str | None = None
    business_name: str | None = None
    tax_form_type: str | None = None
    documents: list[AffiliateDocumentOut] = []
    payout_eligibility: PayoutEligibilityOut
