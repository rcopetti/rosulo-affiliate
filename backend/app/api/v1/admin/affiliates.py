import asyncio
import mimetypes
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.db.dependencies import get_db
from app.db.models import AffiliateDocument, Tenant
from app.schemas.affiliate import AffiliateOut
from app.schemas.affiliate_invite import AffiliateInviteCreate, AffiliateInviteOut
from app.services import affiliate as affiliate_service
from app.services import affiliate_invite as invite_service
from app.services.document_storage import get_document

router = APIRouter()


@router.post("", response_model=AffiliateInviteOut)
async def admin_create_invite(data: AffiliateInviteCreate, tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await invite_service.create_invite(db, tenant, data)


@router.get("", response_model=list[AffiliateOut])
async def admin_list_affiliates(tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await affiliate_service.list_affiliates(db, tenant)


@router.get("/{affiliate_id}", response_model=AffiliateOut)
async def admin_get_affiliate(affiliate_id: str, tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await affiliate_service.get_affiliate(db, uuid.UUID(affiliate_id), tenant)


@router.get("/{affiliate_id}/documents/{document_id}/view")
async def admin_view_document(affiliate_id: str, document_id: str, tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    affiliate = await affiliate_service.get_affiliate(db, uuid.UUID(affiliate_id), tenant)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    try:
        parsed_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    result = await db.execute(select(AffiliateDocument).where(
        AffiliateDocument.id == parsed_id,
        AffiliateDocument.affiliate_account_id == affiliate["affiliate_account_id"],
    ))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    content = await asyncio.to_thread(get_document, document.document_url, document.id)
    return Response(content=content, media_type=document.content_type or mimetypes.guess_type(document.document_url)[0] or "application/octet-stream", headers={
        "Content-Disposition": "inline", "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache", "X-Content-Type-Options": "nosniff",
    })


@router.post("/{affiliate_id}/approve", response_model=AffiliateOut)
async def admin_approve_affiliate(affiliate_id: str, tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await affiliate_service.approve_affiliate_kyc(db, uuid.UUID(affiliate_id), tenant)


@router.post("/{affiliate_id}/reject", response_model=AffiliateOut)
async def admin_reject_affiliate(affiliate_id: str, tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await affiliate_service.reject_affiliate_kyc(db, uuid.UUID(affiliate_id), tenant)
