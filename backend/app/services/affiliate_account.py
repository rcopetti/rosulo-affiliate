import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import Affiliate, AffiliateAccount, AffiliateDocument, Contract, Tenant, Term
from app.schemas.affiliate_account import AffiliateAccountCreate, AffiliateAccountUpdate
from app.schemas.auth import AffiliateLogin, AffiliateRegister


async def register_account(db: AsyncSession, data: AffiliateRegister) -> AffiliateAccount:
    existing = await db.execute(select(AffiliateAccount).where(AffiliateAccount.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    account = AffiliateAccount(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        country=data.country,
        state=data.state,
        postal_code=data.postal_code,
        tax_status=data.tax_status,
        tax_form_type=data.tax_form_type,
        paypal_email=data.paypal_email,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def authenticate_account(db: AsyncSession, data: AffiliateLogin) -> AffiliateAccount:
    result = await db.execute(select(AffiliateAccount).where(AffiliateAccount.email == data.email))
    account = result.scalar_one_or_none()
    if not account or not verify_password(data.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return account


async def update_account(
    db: AsyncSession, account: AffiliateAccount, data: AffiliateAccountUpdate
) -> AffiliateAccount:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    await db.commit()
    await db.refresh(account)
    return account


async def create_tenant_affiliate(
    db: AsyncSession,
    tenant: Tenant,
    data: AffiliateAccountCreate,
    contract_terms: list[dict] | None = None,
) -> Affiliate:
    existing = await db.execute(select(AffiliateAccount).where(AffiliateAccount.email == data.email))
    account = existing.scalar_one_or_none()
    if contract_terms is None:
        contract_terms = [{"commission_percent": 10.0, "payment_sequence": 1}]

    if not account:
        account = AffiliateAccount(
            email=data.email,
            password_hash=hash_password(data.password or "changeme"),
            name=data.name,
            country=data.country,
            state=data.state,
            postal_code=data.postal_code,
            tax_id=data.tax_id,
            tax_status=data.tax_status,
            tax_form_type=data.tax_form_type,
            paypal_email=data.paypal_email,
            backup_withholding_required=data.backup_withholding_required,
        )
        db.add(account)
        await db.flush()

    conflict = await db.execute(
        select(Affiliate).where(
            Affiliate.affiliate_account_id == account.id,
            Affiliate.tenant_id == tenant.id,
        )
    )
    if conflict.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Affiliate already linked to this tenant")

    affiliate = Affiliate(
        affiliate_account_id=account.id,
        tenant_id=tenant.id,
    )
    db.add(affiliate)
    await db.flush()

    contract = Contract(affiliate_id=affiliate.id, active=True)
    db.add(contract)
    await db.flush()

    for term in contract_terms:
        db.add(
            Term(
                contract_id=contract.id,
                payment_sequence=term.get("payment_sequence"),
                sequence_pattern=term.get("sequence_pattern", "*"),
                commission_percent=term["commission_percent"],
                minimum_threshold=term.get("minimum_threshold"),
                effective_from=term.get("effective_from") or date.today(),
                effective_to=term.get("effective_to"),
            )
        )
    await db.commit()
    await db.refresh(affiliate)
    return affiliate


async def add_document(
    db: AsyncSession, account: AffiliateAccount, document_type: str, document_url: str
) -> AffiliateDocument:
    doc = AffiliateDocument(
        affiliate_account_id=account.id,
        document_type=document_type,
        document_url=document_url,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc
