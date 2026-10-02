from decimal import Decimal

import pytest

from app.db.models import AffiliateAccount
from app.services.tax import apply_tax


@pytest.mark.asyncio
async def test_tax_withholding():
    us = AffiliateAccount(tax_status="us_person", country="US")
    assert apply_tax(us, Decimal("100.00")) == (
        Decimal("100.00"),
        Decimal("0.00"),
        Decimal("100.00"),
    )

    # US persons are never withheld, even when backup withholding is flagged.
    us_backup = AffiliateAccount(
        tax_status="us_person", country="US", backup_withholding_required=True
    )
    assert apply_tax(us_backup, Decimal("100.00"))[1] == Decimal("0.00")

    # Brazilian payees are exempt for both individual and business entities.
    for entity_type in ("individual", "business"):
        brazilian = AffiliateAccount(
            tax_status="foreign_person",
            country="BR",
            tax_entity_type=entity_type,
        )
        assert apply_tax(brazilian, Decimal("100.00"))[1] == Decimal("0.00")

    # Other foreign payees are withheld at the statutory 30% rate.
    non_us = AffiliateAccount(tax_status="foreign_person", country="DE")
    assert apply_tax(non_us, Decimal("100.00"))[1] == Decimal("30.00")
    assert apply_tax(non_us, Decimal("0.05")) == (
        Decimal("0.05"),
        Decimal("0.02"),
        Decimal("0.03"),
    )
