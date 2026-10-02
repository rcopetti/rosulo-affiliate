from sqlalchemy import Numeric

from app.db.base import Base
from app.db.models import (
    Commission,
    Event,
    Payout,
    PayoutCommission,
    PayoutPayment,
    Term,
)


def test_financial_model_columns_use_expected_numeric_precision():
    money_columns = (
        Event.__table__.c.amount,
        Commission.__table__.c.gross_amount,
        Commission.__table__.c.withholding_amount,
        Commission.__table__.c.net_amount,
        Payout.__table__.c.requested_amount,
        Payout.__table__.c.approved_amount,
        Payout.__table__.c.withholding_total,
        Payout.__table__.c.paypal_fees,
        Payout.__table__.c.net_paid,
        PayoutCommission.__table__.c.amount,
        PayoutPayment.__table__.c.amount,
        Term.__table__.c.minimum_threshold,
    )
    for column in money_columns:
        assert type(column.type) is Numeric
        assert column.type.precision == 20
        assert column.type.scale == 2

    assert type(Term.__table__.c.commission_percent.type) is Numeric
    assert Term.__table__.c.commission_percent.type.precision == 9
    assert Term.__table__.c.commission_percent.type.scale == 6


def test_legacy_payment_record_mapping_is_retired():
    assert "payment_records" not in Base.metadata.tables
    assert PayoutPayment.__tablename__ == "payout_payments"
    # Sale events keep the merchant's external correlation string even though
    # the payment_records table it once named is gone.
    assert "payment_record_id" in Event.__table__.c
