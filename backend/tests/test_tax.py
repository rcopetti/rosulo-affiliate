from decimal import Decimal

import pytest

from app.db.models import AffiliateAccount
from app.services.tax import apply_tax


@pytest.mark.asyncio
async def test_tax_withholding():
    us = AffiliateAccount(tax_status="us_person", backup_withholding_required=False)
    assert apply_tax(us, Decimal("100.00")) == (
        Decimal("100.00"),
        Decimal("0.00"),
        Decimal("100.00"),
    )

    us_backup = AffiliateAccount(tax_status="us_person", backup_withholding_required=True)
    assert apply_tax(us_backup, Decimal("100.00"))[1] == Decimal("24.00")

    non_us = AffiliateAccount(tax_status="non_us_person", backup_withholding_required=False)
    assert apply_tax(non_us, Decimal("100.00"))[1] == Decimal("30.00")
    assert apply_tax(non_us, Decimal("0.05")) == (
        Decimal("0.05"),
        Decimal("0.02"),
        Decimal("0.03"),
    )
