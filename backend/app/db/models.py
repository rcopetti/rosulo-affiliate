import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    api_key_hash = Column(String, nullable=False, unique=True)
    allowed_domains = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    users = relationship("TenantUser", back_populates="tenant")
    invites = relationship("AffiliateInvite", back_populates="tenant")


class TenantUser(Base):
    __tablename__ = "tenant_users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    role = Column(String, nullable=False, default="admin")
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    tenant = relationship("Tenant", back_populates="users")


class AffiliateInvite(Base):
    __tablename__ = "affiliate_invites"
    __table_args__ = (UniqueConstraint("tenant_id", "token"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String, nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    contract_terms = Column(JSON, default=list)
    status = Column(String, nullable=False, default="pending")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    tenant = relationship("Tenant", back_populates="invites")


class AffiliateAccount(Base):
    __tablename__ = "affiliate_accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    country = Column(String, nullable=False)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    tax_status = Column(String, nullable=False, default="us_person")
    tax_entity_type = Column(String, nullable=False, default="individual")
    business_name = Column(String, nullable=True)
    tax_form_type = Column(String, nullable=True)
    withholding_certificate = Column(String, nullable=True)
    backup_withholding_required = Column(Boolean, default=False)
    paypal_email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    affiliates = relationship("Affiliate", back_populates="account")
    documents = relationship("AffiliateDocument", back_populates="account")


class Affiliate(Base):
    __tablename__ = "affiliates"
    __table_args__ = (UniqueConstraint("affiliate_account_id", "tenant_id"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_account_id = Column(
        UUID(as_uuid=True), ForeignKey("affiliate_accounts.id"), nullable=False
    )
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    kyc_approved_for_payout = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    account = relationship("AffiliateAccount", back_populates="affiliates")
    campaigns = relationship("Campaign", back_populates="affiliate")
    commissions = relationship("Commission", back_populates="affiliate")
    payouts = relationship("Payout", back_populates="affiliate")
    contracts = relationship("Contract", back_populates="affiliate")


class AffiliateDocument(Base):
    __tablename__ = "affiliate_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_account_id = Column(
        UUID(as_uuid=True), ForeignKey("affiliate_accounts.id"), nullable=False
    )
    document_type = Column(String, nullable=False)
    document_url = Column(String, nullable=False)  # private S3 object key
    content_type = Column(String, nullable=False, default="application/octet-stream")
    file_size = Column(Integer, nullable=False, default=0)
    approved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    account = relationship("AffiliateAccount", back_populates="documents")


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_id = Column(UUID(as_uuid=True), ForeignKey("affiliates.id"), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    affiliate = relationship("Affiliate", back_populates="contracts")
    terms = relationship("Term", back_populates="contract", lazy="selectin")


class Term(Base):
    __tablename__ = "terms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    payment_sequence = Column(Integer, nullable=True)
    sequence_pattern = Column(String, nullable=False, default="*")
    commission_percent = Column(Float, nullable=False)
    minimum_threshold = Column(Float, nullable=True)
    effective_from = Column(Date, default=lambda: datetime.date.today())
    effective_to = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)

    contract = relationship("Contract", back_populates="terms")


class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_id = Column(UUID(as_uuid=True), ForeignKey("affiliates.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    tracking_code = Column(String, unique=True, nullable=False, index=True)
    landing_url = Column(String, nullable=False)
    name = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    affiliate = relationship("Affiliate", back_populates="campaigns")
    events = relationship("Event", back_populates="campaign")


class Event(Base):
    __tablename__ = "events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String, unique=True, nullable=False, index=True)
    type = Column(String, nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    affiliate_id = Column(UUID(as_uuid=True), ForeignKey("affiliates.id"), nullable=True)
    customer_id = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    amount = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    payment_sequence = Column(Integer, default=1)
    good_date = Column(Date, nullable=True)
    payment_record_id = Column(String, nullable=True)
    referer = Column(String, nullable=True)
    page_url = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=now_utc)
    created_at = Column(DateTime(timezone=True), default=now_utc)

    campaign = relationship("Campaign", back_populates="events")
    commissions = relationship("Commission", back_populates="event")


class PaymentRecord(Base):
    __tablename__ = "payment_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_payment_id = Column(String, nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    customer_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    paid_at = Column(DateTime(timezone=True), default=now_utc)
    sequence_number = Column(Integer, default=1)
    status = Column(String, default="paid")
    created_at = Column(DateTime(timezone=True), default=now_utc)


class Commission(Base):
    __tablename__ = "commissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    affiliate_id = Column(UUID(as_uuid=True), ForeignKey("affiliates.id"), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    gross_amount = Column(Float, default=0.0)
    withholding_amount = Column(Float, default=0.0)
    net_amount = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    status = Column(String, default="pending")
    available_on = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    event = relationship("Event", back_populates="commissions")
    affiliate = relationship("Affiliate", back_populates="commissions")
    payout_commissions = relationship("PayoutCommission", back_populates="commission")


class Payout(Base):
    __tablename__ = "payouts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_id = Column(UUID(as_uuid=True), ForeignKey("affiliates.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    requested_amount = Column(Float, default=0.0)
    approved_amount = Column(Float, default=0.0)
    withholding_total = Column(Float, default=0.0)
    paypal_fees = Column(Float, default=0.0)
    net_paid = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    paypal_batch_id = Column(String, nullable=True)
    status = Column(String, default="requested")
    requested_at = Column(DateTime(timezone=True), default=now_utc)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    affiliate = relationship("Affiliate", back_populates="payouts", lazy="selectin")
    payout_commissions = relationship("PayoutCommission", back_populates="payout", lazy="selectin")


class PayoutCommission(Base):
    __tablename__ = "payout_commissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payout_id = Column(UUID(as_uuid=True), ForeignKey("payouts.id"), nullable=False)
    commission_id = Column(UUID(as_uuid=True), ForeignKey("commissions.id"), nullable=False)
    amount = Column(Float, default=0.0)

    payout = relationship("Payout", back_populates="payout_commissions")
    commission = relationship("Commission", back_populates="payout_commissions")
