from app.services.tax_profile import derive_tax_form_type


def test_derive_tax_form_type():
    assert derive_tax_form_type("us_person", "individual") == "W-9"
    assert derive_tax_form_type("us_person", "business") == "W-9"
    assert derive_tax_form_type("foreign_person", "individual") == "W-8BEN"
    assert derive_tax_form_type("foreign_person", "business") == "W-8BEN-E"
