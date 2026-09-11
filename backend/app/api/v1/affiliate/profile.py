import asyncio
import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate_account
from app.core.config import settings
from app.db.dependencies import get_db
from app.db.models import AffiliateAccount, AffiliateDocument
from app.schemas.affiliate_account import AffiliateAccountOut, AffiliateAccountUpdate
from app.services import affiliate_account as acct_service
from app.services.document_storage import get_document
from app.services.tax_profile import derive_tax_form_type

router = APIRouter()


@router.get("/profile", response_model=AffiliateAccountOut)
async def get_profile(account: AffiliateAccount = Depends(get_current_affiliate_account)):
    return account


@router.patch("/profile", response_model=AffiliateAccountOut)
async def update_profile(
    data: AffiliateAccountUpdate,
    account: AffiliateAccount = Depends(get_current_affiliate_account),
    db: AsyncSession = Depends(get_db),
):
    return await acct_service.update_account(db, account, data)


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(..., alias="type"),
    account: AffiliateAccount = Depends(get_current_affiliate_account),
    db: AsyncSession = Depends(get_db),
):
    expected = derive_tax_form_type(account.tax_status, account.tax_entity_type)
    if document_type != expected:
        raise HTTPException(status_code=400, detail=f"Expected document type {expected}")
    if file.content_type not in {"application/pdf", "image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Only PDF, JPEG, PNG, and WebP documents are supported")
    content = await file.read(settings.documents_max_bytes + 1)
    if len(content) > settings.documents_max_bytes:
        raise HTTPException(status_code=413, detail="Document exceeds the maximum allowed size")
    document = await acct_service.add_document(
        db, account, document_type, content, file.content_type
    )
    return {"id": str(document.id), "document_type": document.document_type, "status": "pending"}


@router.get("/documents/{document_id}/view")
async def view_document(
    document_id: str,
    account: AffiliateAccount = Depends(get_current_affiliate_account),
    db: AsyncSession = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    result = await db.execute(select(AffiliateDocument).where(
        AffiliateDocument.id == parsed_id,
        AffiliateDocument.affiliate_account_id == account.id,
    ))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    content = await asyncio.to_thread(get_document, document.document_url, document.id)
    media_type = document.content_type or mimetypes.guess_type(document.document_url)[0] or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
