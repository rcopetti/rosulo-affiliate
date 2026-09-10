import datetime
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AffiliateAccount, AffiliateInvite, Tenant
from app.schemas.affiliate_account import AffiliateAccountCreate
from app.schemas.affiliate_invite import AffiliateInviteAccept, AffiliateInviteCreate
from app.services import affiliate_account as acct_service
from app.services import email as email_service


async def create_invite(
    db: AsyncSession, tenant: Tenant, data: AffiliateInviteCreate
) -> AffiliateInvite:
    token = secrets.token_urlsafe(32)
    terms = data.contract_terms or [{"commission_percent": 10.0, "payment_sequence": 1}]
    invite = AffiliateInvite(
        tenant_id=tenant.id,
        email=data.email,
        token=token,
        contract_terms=terms,
        status="pending",
        expires_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=7),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    await email_service.send_invite_email(invite, tenant.name)
    return invite


async def _get_valid_invite(db: AsyncSession, token: str, email: str) -> AffiliateInvite:
    result = await db.execute(
        select(AffiliateInvite).where(
            AffiliateInvite.token == token,
            AffiliateInvite.email == email,
            AffiliateInvite.status == "pending",
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invite")
    if invite.expires_at and invite.expires_at < datetime.datetime.now(
        datetime.timezone.utc
    ):
        raise HTTPException(status_code=400, detail="Invite expired")
    return invite


async def accept_invite(
    db: AsyncSession, data: AffiliateInviteAccept
) -> tuple[AffiliateAccount, Tenant]:
    invite = await _get_valid_invite(db, data.token, data.email)

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == invite.tenant_id)
    )
    tenant = tenant_result.scalar_one()

    existing = await db.execute(
        select(AffiliateAccount).where(AffiliateAccount.email == data.email)
    )
    account = existing.scalar_one_or_none()

    if account:
        # association invite: registration fields are ignored
        acct_data = AffiliateAccountCreate(
            email=data.email,
            password="changeme",
            name=account.name,
            country=account.country,
            state=data.state or account.state,
            tax_id=account.tax_id,
            tax_status=data.tax_status or account.tax_status,
            tax_form_type=data.tax_form_type or account.tax_form_type,
            paypal_email=data.paypal_email or account.paypal_email,
            backup_withholding_required=account.backup_withholding_required,
        )
    else:
        if not data.password or not data.name or not data.country:
            raise HTTPException(
                status_code=400,
                detail="password, name, and country are required for registration invite",
            )
        acct_data = AffiliateAccountCreate(
            email=data.email,
            password=data.password,
            name=data.name,
            country=data.country,
            state=data.state,
            tax_status=data.tax_status,
            tax_form_type=data.tax_form_type,
            paypal_email=data.paypal_email,
        )

    await acct_service.create_tenant_affiliate(
        db, tenant, acct_data, contract_terms=invite.contract_terms
    )

    # Reload account after commit
    account_result = await db.execute(
        select(AffiliateAccount).where(AffiliateAccount.email == data.email)
    )
    account = account_result.scalar_one()

    invite.status = "accepted"
    await db.commit()

    return account, tenant


async def accept_invite_token(
    db: AsyncSession, account: AffiliateAccount, token: str
) -> None:
    invite = await _get_valid_invite(db, token, account.email)

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == invite.tenant_id)
    )
    tenant = tenant_result.scalar_one()

    acct_data = AffiliateAccountCreate(
        email=account.email,
        password="changeme",
        name=account.name,
        country=account.country,
        state=account.state,
        tax_id=account.tax_id,
        tax_status=account.tax_status,
        tax_form_type=account.tax_form_type,
        paypal_email=account.paypal_email,
        backup_withholding_required=account.backup_withholding_required,
    )

    await acct_service.create_tenant_affiliate(
        db, tenant, acct_data, contract_terms=invite.contract_terms
    )

    invite.status = "accepted"
    await db.commit()


async def pending_invites(db: AsyncSession, account: AffiliateAccount) -> list[dict]:
    now = datetime.datetime.now(datetime.timezone.utc)
    result = await db.execute(
        select(AffiliateInvite, Tenant)
        .join(Tenant, AffiliateInvite.tenant_id == Tenant.id)
        .where(
            AffiliateInvite.email == account.email,
            AffiliateInvite.status == "pending",
            (AffiliateInvite.expires_at == None)
            | (AffiliateInvite.expires_at > now),
        )
    )
    return [
        {
            "id": str(i.id),
            "tenant_id": str(t.id),
            "tenant_name": t.name,
            "token": i.token,
            "expires_at": i.expires_at.isoformat() if i.expires_at else None,
        }
        for i, t in result.all()
    ]
