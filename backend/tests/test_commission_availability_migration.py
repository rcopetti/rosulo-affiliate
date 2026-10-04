import importlib.util
import uuid
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core.security import hash_api_key
from app.db.models import (
    Affiliate,
    AffiliateAccount,
    Campaign,
    Commission,
    Event,
    Payout,
    PayoutCommission,
    Tenant,
)
from app.db.session import async_session, engine

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "e8f9a0b1c2d3_commission_availability_and_reservations.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "e8f9a0b1c2d3_commission_availability_and_reservations", MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration_module()


async def _run_preflight():
    async with engine.begin() as conn:
        await conn.run_sync(MIGRATION.run_preflight)


async def _drop_sale_context_constraint():
    # ck_events_sale_payment_context only exists from a1b2c3d4e5f6 onward;
    # these preflights emulate the earlier revision where invalid sale events
    # could still be stored.
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "ALTER TABLE events "
                "DROP CONSTRAINT ck_events_sale_payment_context"
            )
        )


async def _create_sale_commission(
    session,
    *,
    good_date=date(2026, 1, 15),
    payment_record_id="external-pay-1",
):
    tenant = Tenant(name="acme", api_key_hash=hash_api_key(f"key-{uuid.uuid4()}"))
    account = AffiliateAccount(
        email=f"affiliate-{uuid.uuid4()}@example.com",
        password_hash="hash",
        name="Affiliate",
        country="US",
    )
    session.add_all([tenant, account])
    await session.flush()
    affiliate = Affiliate(affiliate_account_id=account.id, tenant_id=tenant.id)
    session.add(affiliate)
    await session.flush()
    campaign = Campaign(
        affiliate_id=affiliate.id,
        tenant_id=tenant.id,
        tracking_code=f"trk-{uuid.uuid4()}",
        landing_url="https://example.com/landing",
    )
    event = Event(
        event_id=f"sale-{uuid.uuid4()}",
        type="sale",
        tenant_id=tenant.id,
        campaign_id=campaign.id,
        affiliate_id=affiliate.id,
        good_date=good_date,
        payment_record_id=payment_record_id,
    )
    session.add_all([campaign, event])
    await session.flush()
    commission = Commission(
        event_id=event.id,
        affiliate_id=affiliate.id,
        campaign_id=campaign.id,
        status="pending",
    )
    session.add(commission)
    await session.flush()
    return tenant, affiliate, commission


async def _create_payout(session, affiliate, tenant, status="pending_approval"):
    payout = Payout(affiliate_id=affiliate.id, tenant_id=tenant.id, status=status)
    session.add(payout)
    await session.flush()
    return payout


@pytest.mark.asyncio
async def test_preflight_rejects_sale_event_missing_good_date():
    await _drop_sale_context_constraint()
    async with async_session() as session:
        await _create_sale_commission(session, good_date=None)
        await session.commit()

    with pytest.raises(RuntimeError, match="good_date"):
        await _run_preflight()


@pytest.mark.asyncio
@pytest.mark.parametrize("payment_record_id", [None, "", "   "])
async def test_preflight_rejects_sale_event_missing_payment_record_id(
    payment_record_id,
):
    await _drop_sale_context_constraint()
    async with async_session() as session:
        await _create_sale_commission(session, payment_record_id=payment_record_id)
        await session.commit()

    with pytest.raises(RuntimeError, match="payment_record_id"):
        await _run_preflight()


@pytest.mark.asyncio
async def test_preflight_rejects_commission_linked_to_two_active_payouts():
    async with async_session() as session:
        tenant, affiliate, commission = await _create_sale_commission(session)
        first = await _create_payout(session, affiliate, tenant, status="pending_approval")
        second = await _create_payout(session, affiliate, tenant, status="approved")
        session.add_all(
            [
                PayoutCommission(payout_id=first.id, commission_id=commission.id),
                PayoutCommission(payout_id=second.id, commission_id=commission.id),
            ]
        )
        await session.commit()

    with pytest.raises(RuntimeError, match="more than one"):
        await _run_preflight()


@pytest.mark.asyncio
@pytest.mark.parametrize("active_status", ["pending_approval", "approved"])
@pytest.mark.parametrize("closed_status", ["paid", "rejected"])
async def test_preflight_accepts_commission_linked_to_one_active_and_one_closed_payout(
    active_status,
    closed_status,
):
    async with async_session() as session:
        tenant, affiliate, commission = await _create_sale_commission(session)
        active = await _create_payout(session, affiliate, tenant, status=active_status)
        closed = await _create_payout(session, affiliate, tenant, status=closed_status)
        session.add_all(
            [
                PayoutCommission(payout_id=active.id, commission_id=commission.id),
                PayoutCommission(payout_id=closed.id, commission_id=commission.id),
            ]
        )
        await session.commit()

    await _run_preflight()


@pytest.mark.asyncio
async def test_preflight_rejects_legacy_payout_status():
    # ck_payouts_status only exists from f9a0b1c2d3e4 onward; this preflight
    # guards the earlier revision where legacy statuses could still be stored.
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("ALTER TABLE payouts DROP CONSTRAINT ck_payouts_status")
        )
    async with async_session() as session:
        tenant, affiliate, _ = await _create_sale_commission(session)
        await _create_payout(session, affiliate, tenant, status="requested")
        await session.commit()

    with pytest.raises(RuntimeError, match="payouts have a status"):
        await _run_preflight()


@pytest.mark.asyncio
@pytest.mark.parametrize("payout_status", ["pending_approval", "approved"])
async def test_preflight_requires_pending_status_for_commission_linked_to_active_payout(
    payout_status,
):
    """A commission linked to an in-flight payout must still be stored
    `pending`; any other status (e.g. `available`) would wedge reject/confirm
    once the link is backfilled is_active."""
    async with async_session() as session:
        tenant, affiliate, commission = await _create_sale_commission(session)
        commission.status = "available"
        payout = await _create_payout(
            session, affiliate, tenant, status=payout_status
        )
        session.add(
            PayoutCommission(payout_id=payout.id, commission_id=commission.id)
        )
        await session.commit()
        commission_id = commission.id

    with pytest.raises(RuntimeError, match="not stored pending"):
        await _run_preflight()

    async with async_session() as session:
        commission = await session.get(Commission, commission_id)
        commission.status = "pending"
        await session.commit()

    await _run_preflight()


@pytest.mark.asyncio
async def test_preflight_accepts_clean_data():
    async with async_session() as session:
        tenant, affiliate, commission = await _create_sale_commission(session)
        payout = await _create_payout(session, affiliate, tenant, status="pending_approval")
        session.add(PayoutCommission(payout_id=payout.id, commission_id=commission.id))
        await session.commit()

    await _run_preflight()


def test_commission_availability_model_contract():
    available_at = Commission.__table__.c.available_at
    assert isinstance(available_at.type, sa.DateTime)
    assert available_at.type.timezone is True
    assert available_at.nullable is True

    assert "ck_commissions_status" in {
        constraint.name for constraint in Commission.__table__.constraints
    }

    is_active = PayoutCommission.__table__.c.is_active
    assert is_active.nullable is False
    assert is_active.server_default is not None

    index = next(
        idx
        for idx in PayoutCommission.__table__.indexes
        if idx.name == "uq_payout_commissions_active_commission"
    )
    assert index.unique is True

    where_clause = index.dialect_options["postgresql"]["where"]
    assert where_clause is not None
    assert "is_active" in str(
        where_clause.compile(compile_kwargs={"literal_binds": True})
    )
