import datetime
import uuid

from pydantic import AliasPath, BaseModel, ConfigDict, Field

from app.schemas.payout import PayoutStatus


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


class AffiliatePayoutHistoryItem(BaseModel):
    """One payout row in an affiliate's history; the payment reference is
    resolved from the recorded ``PayoutPayment`` when the payout is paid."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: PayoutStatus
    currency: str
    requested_amount: float
    approved_amount: float
    withholding_total: float
    net_paid: float
    requested_at: datetime.datetime
    approved_at: datetime.datetime | None = None
    paid_at: datetime.datetime | None = None
    payment_reference: str | None = Field(
        default=None,
        validation_alias=AliasPath("payout_payment", "transfer_reference"),
    )


class AffiliatePaidCurrencyTotals(BaseModel):
    """Paid ``PayoutPayment`` totals for one currency.

    ``rolling_12_months`` covers ``paid_at >=`` the same UTC date one year
    ago (Feb 28 when the prior year has no Feb 29); ``year_to_date`` covers
    ``paid_at >=`` UTC Jan 1 of the current year. Currencies are never
    summed together.
    """

    currency: str
    rolling_12_months: float
    year_to_date: float


class AffiliatePayoutHistory(BaseModel):
    items: list[AffiliatePayoutHistoryItem]
    total: int
    limit: int
    offset: int
    paid_totals_by_currency: list[AffiliatePaidCurrencyTotals]
