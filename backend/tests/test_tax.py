import pytest
from app.services.tax import apply_tax
from app.db.models import AffiliateAccount


@pytest.mark.asyncio
async def test_tax_withholding():
    us = AffiliateAccount(tax_status="us_person", backup_withholding_required=False)
    assert apply_tax(us, 100.0)[1:] == (0.0, 100.0)

    us_backup = AffiliateAccount(tax_status="us_person", backup_withholding_required=True)
    assert apply_tax(us_backup, 100.0)[1] == 24.0

    non_us = AffiliateAccount(tax_status="non_us_person", backup_withholding_required=False)
    assert apply_tax(non_us, 100.0)[1] == 30.0
