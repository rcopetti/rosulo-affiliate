from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Affiliate,
    AffiliateAccount,
    AffiliateDocument,
    AffiliateDocumentReview,
    TenantUser,
)
from app.services.tax_profile import derive_tax_form_type


def _document_status(document: AffiliateDocument) -> str:
    return document.review_decisions[-1].status if document.review_decisions else "pending"


def _document_out(document: AffiliateDocument) -> dict:
    reviews = document.review_decisions
    return {
        "id": document.id,
        "document_type": document.document_type,
        "content_type": document.content_type,
        "created_at": document.created_at,
        "status": _document_status(document),
        "review_history": [
            {
                "status": review.status,
                "reviewed_at": review.reviewed_at,
                "rejection_reason": review.rejection_reason,
                "reviewer": {
                    "id": review.reviewer.id,
                    "name": review.reviewer.name,
                    "email": review.reviewer.email,
                },
            }
            for review in reviews
        ],
    }


async def review_document(
    db: AsyncSession,
    affiliate_id,
    document_id,
    reviewer: TenantUser,
    status: str,
    rejection_reason: str | None,
) -> dict | None:
    result = await db.execute(
        select(AffiliateDocument)
        .join(Affiliate, AffiliateDocument.affiliate_id == Affiliate.id)
        .where(
            AffiliateDocument.id == document_id,
            Affiliate.id == affiliate_id,
            Affiliate.tenant_id == reviewer.tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        return None

    db.add(
        AffiliateDocumentReview(
            document_id=document.id,
            reviewer_id=reviewer.id,
            status=status,
            rejection_reason=rejection_reason,
        )
    )
    await db.commit()
    affiliate = await db.get(Affiliate, affiliate_id)
    return await get_document_status(db, affiliate)


async def get_document_status(db: AsyncSession, affiliate: Affiliate) -> dict:
    account = await db.get(AffiliateAccount, affiliate.affiliate_account_id)
    required_type = derive_tax_form_type(account.tax_status, account.tax_entity_type)
    result = await db.execute(
        select(AffiliateDocument)
        .options(
            selectinload(AffiliateDocument.review_decisions).selectinload(
                AffiliateDocumentReview.reviewer
            )
        )
        .where(AffiliateDocument.affiliate_id == affiliate.id)
        .order_by(AffiliateDocument.created_at, AffiliateDocument.id)
    )
    documents = result.scalars().all()
    required_documents = [doc for doc in documents if doc.document_type == required_type]

    if not required_documents:
        eligibility = {
            "eligible": False,
            "status": "missing",
            "reason": "Required tax document is missing",
        }
    else:
        latest = required_documents[-1]
        status = _document_status(latest)
        eligibility = {
            "eligible": status == "approved",
            "status": status,
            "reason": (
                latest.review_decisions[-1].rejection_reason
                if status == "rejected"
                else None if status == "approved" else "Required tax document is awaiting review"
            ),
        }

    return {
        "required_document_type": required_type,
        "documents": [_document_out(document) for document in reversed(documents)],
        "payout_eligibility": eligibility,
    }
