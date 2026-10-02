from datetime import date, datetime, timezone

import pytest

from app.db.models import Commission
from app.services.commission import mature_due_commissions

JUST_AFTER_DUE = datetime(2026, 10, 1, 0, 15, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_maturity_promotes_only_due_pending_commissions(payout_scenario):
    due_id = await payout_scenario.create_commission(date(2026, 10, 1), "payment-due-1")
    future_id = await payout_scenario.create_commission(date(2026, 10, 2), "payment-future-1")

    async with payout_scenario.db_session() as db:
        promoted = await mature_due_commissions(
            db,
            now_utc=datetime(2026, 10, 1, 0, 15, tzinfo=timezone.utc),
        )

    assert promoted == 1
    assert await payout_scenario.commission_status(due_id) == "available"
    assert await payout_scenario.commission_status(future_id) == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("payout_status", ["pending_approval", "approved"])
async def test_maturity_skips_commissions_reserved_by_legacy_payout_status(
    payout_scenario, payout_status
):
    """Old app versions expressed a reservation only through the parent payout
    status while PayoutCommission.is_active kept its false default; a due
    pending commission linked to such a payout must not be promoted."""
    reserved_id = await payout_scenario.create_commission(
        date(2026, 10, 1), f"payment-reserved-{payout_status}"
    )
    await payout_scenario.add_legacy_active_payout(
        reserved_id, payout_status=payout_status, is_active=False
    )

    async with payout_scenario.db_session() as db:
        promoted = await mature_due_commissions(db, now_utc=JUST_AFTER_DUE)

    assert promoted == 0
    assert await payout_scenario.commission_status(reserved_id) == "pending"


@pytest.mark.asyncio
async def test_maturity_skips_commissions_with_active_reservation_flag(payout_scenario):
    """An active PayoutCommission link blocks promotion even when the parent
    payout itself is already closed."""
    reserved_id = await payout_scenario.create_commission(date(2026, 10, 1), "payment-flagged-1")
    await payout_scenario.add_legacy_active_payout(
        reserved_id, payout_status="rejected", is_active=True
    )

    async with payout_scenario.db_session() as db:
        promoted = await mature_due_commissions(db, now_utc=JUST_AFTER_DUE)

    assert promoted == 0
    assert await payout_scenario.commission_status(reserved_id) == "pending"


@pytest.mark.asyncio
async def test_maturity_is_idempotent_across_repeated_runs(payout_scenario):
    due_id = await payout_scenario.create_commission(date(2026, 10, 1), "payment-repeat-1")
    future_id = await payout_scenario.create_commission(date(2026, 10, 2), "payment-repeat-2")

    async with payout_scenario.db_session() as db:
        first = await mature_due_commissions(db, now_utc=JUST_AFTER_DUE)
        second = await mature_due_commissions(db, now_utc=JUST_AFTER_DUE)

    assert first == 1
    assert second == 0
    assert await payout_scenario.commission_status(due_id) == "available"
    assert await payout_scenario.commission_status(future_id) == "pending"


@pytest.mark.asyncio
async def test_maturity_backfills_null_available_at_from_event_good_date(
    payout_scenario,
):
    """Rows written by an older app version after the expand migration may
    carry a null available_at (and a good_date+14 available_on); the job
    derives UTC midnight from Event.good_date and mirrors it into
    available_on."""
    legacy_due_id = await payout_scenario.create_commission(
        date(2026, 10, 1),
        "payment-legacy-due",
        available_at=None,
        available_on=date(2026, 10, 15),
    )
    legacy_future_id = await payout_scenario.create_commission(
        date(2026, 10, 5),
        "payment-legacy-future",
        available_at=None,
        available_on=date(2026, 10, 19),
    )

    async with payout_scenario.db_session() as db:
        promoted = await mature_due_commissions(db, now_utc=JUST_AFTER_DUE)
        due_row = await db.get(Commission, legacy_due_id)
        future_row = await db.get(Commission, legacy_future_id)

    assert promoted == 1
    assert due_row.status == "available"
    assert due_row.available_at == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert due_row.available_on == date(2026, 10, 1)
    assert future_row.status == "pending"
    assert future_row.available_at == datetime(2026, 10, 5, tzinfo=timezone.utc)
    assert future_row.available_on == date(2026, 10, 5)


@pytest.mark.asyncio
async def test_maturity_leaves_non_pending_statuses_untouched(payout_scenario):
    for status in ("available", "reserved", "paid", "reversed"):
        await payout_scenario.create_commission(
            date(2026, 10, 1), f"payment-{status}-1", status=status
        )

    async with payout_scenario.db_session() as db:
        promoted = await mature_due_commissions(db, now_utc=JUST_AFTER_DUE)

    assert promoted == 0
