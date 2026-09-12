from typing import Literal

TaxStatus = Literal["us_person", "foreign_person"]
TaxEntityType = Literal["individual", "business"]


def derive_tax_form_type(tax_status: str | None, tax_entity_type: str | None) -> str:
    """Return the IRS document expected from the selected payee classification."""
    if tax_status == "foreign_person":
        return "W-8BEN-E" if tax_entity_type == "business" else "W-8BEN"
    return "W-9"
