from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.balance import add_legacy_balance_fields, build_balances, get_balances


def test_build_balances_groups_currencies_and_keeps_reversal_separate():
    balances = build_balances(
        [
            ("USD", "pending", Decimal("1.00"), Decimal("9.00")),
            ("USD", "available", Decimal("0.00"), Decimal("5.00")),
            ("USD", "reserved", Decimal("0.00"), Decimal("4.00")),
            ("USD", "paid", Decimal("0.00"), Decimal("20.00")),
            ("USD", "reversed", Decimal("0.00"), Decimal("-3.00")),
            ("EUR", "available", Decimal("0.00"), Decimal("7.00")),
        ]
    )

    by_currency = {balance["currency"]: balance for balance in balances}
    assert by_currency["USD"]["earned"] == Decimal("35.00")
    assert by_currency["USD"]["pending"] == Decimal("9.00")
    assert by_currency["USD"]["tax_retained"] == Decimal("1.00")
    assert by_currency["USD"]["available"] == Decimal("5.00")
    assert by_currency["USD"]["reserved"] == Decimal("4.00")
    assert by_currency["USD"]["paid"] == Decimal("20.00")
    assert by_currency["USD"]["reversal_total"] == Decimal("3.00")
    assert add_legacy_balance_fields([by_currency["USD"]])["debt"] == Decimal("3.00")
    assert by_currency["EUR"]["earned"] == Decimal("7.00")
    assert by_currency["EUR"]["available"] == Decimal("7.00")


def test_add_legacy_balance_fields_includes_reserved_bucket():
    empty = add_legacy_balance_fields([])
    assert empty["reserved"] == Decimal("0.00")

    multi = add_legacy_balance_fields(
        [
            {
                "currency": "USD",
                "earned": Decimal("1.00"),
                "pending": Decimal("0.00"),
                "available": Decimal("1.00"),
                "reserved": Decimal("0.00"),
                "paid": Decimal("0.00"),
                "reversed": Decimal("0.00"),
                "tax_retained": Decimal("0.00"),
                "reversal_total": Decimal("0.00"),
            },
            {
                "currency": "EUR",
                "earned": Decimal("2.00"),
                "pending": Decimal("0.00"),
                "available": Decimal("0.00"),
                "reserved": Decimal("2.00"),
                "paid": Decimal("0.00"),
                "reversed": Decimal("0.00"),
                "tax_retained": Decimal("0.00"),
                "reversal_total": Decimal("0.00"),
            },
        ]
    )
    assert multi["reserved"] is None


@pytest.mark.asyncio
async def test_get_balances_reports_reserved_and_skips_lazy_promotion(
    payout_scenario,
):
    due = date.today() - timedelta(days=1)
    available_id = await payout_scenario.create_commission(
        due, "bal-avail-1", status="available"
    )
    due_pending_id = await payout_scenario.create_commission(
        due, "bal-pending-1", status="pending"
    )
    reserved_id = await payout_scenario.create_commission(
        due, "bal-reserved-1", status="reserved"
    )
    # Legacy reservation shape: stored pending + a link whose parent payout
    # is still open. The logical status must surface it as reserved.
    legacy_id = await payout_scenario.create_commission(
        due, "bal-legacy-1", status="pending"
    )
    await payout_scenario.add_legacy_active_payout(
        legacy_id, payout_status="pending_approval"
    )

    async with payout_scenario.db_session() as db:
        balances = await get_balances(db, payout_scenario.affiliate_id)

    usd = next(row for row in balances if row["currency"] == "USD")
    assert usd["available"] == Decimal("10.00")
    assert usd["pending"] == Decimal("10.00")
    assert usd["reserved"] == Decimal("20.00")

    # get_balances no longer promotes due rows: that is the daily job's role.
    assert await payout_scenario.commission_status(available_id) == "available"
    assert await payout_scenario.commission_status(due_pending_id) == "pending"
