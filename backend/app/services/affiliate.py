import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Affiliate, Tenant
from app.services.document_review import get_document_status


async def _affiliate_out(db: AsyncSession, affiliate: Affiliate) -> dict:
    document_status = await get_document_status(db, affiliate)
    return {
        "id": affiliate.id,
        "tenant_id": affiliate.tenant_id,
        "affiliate_account_id": affiliate.affiliate_account_id,
        "email": affiliate.account.email,
        "name": affiliate.account.name,
        "country": affiliate.account.country,
        "state": affiliate.account.state,
        "postal_code": affiliate.account.postal_code,
        "paypal_email": affiliate.account.paypal_email,
        "tax_status": affiliate.account.tax_status,
        "tax_entity_type": affiliate.account.tax_entity_type,
        "business_name": affiliate.account.business_name,
        "tax_form_type": affiliate.account.tax_form_type,
        "documents": document_status["documents"],
        "payout_eligibility": document_status["payout_eligibility"],
    }


async def list_affiliates(db: AsyncSession, tenant: Tenant):
    result = await db.execute(
        select(Affiliate)
        .options(selectinload(Affiliate.account))
        .where(Affiliate.tenant_id == tenant.id)
    )
    return [await _affiliate_out(db, affiliate) for affiliate in result.scalars().all()]


async def get_affiliate(db: AsyncSession, affiliate_id: uuid.UUID, tenant: Tenant):
    result = await db.execute(
        select(Affiliate)
        .options(selectinload(Affiliate.account))
        .where(
            Affiliate.id == affiliate_id,
            Affiliate.tenant_id == tenant.id,
        )
    )
    affiliate = result.scalar_one_or_none()
    return await _affiliate_out(db, affiliate) if affiliate else None
