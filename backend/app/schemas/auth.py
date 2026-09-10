from pydantic import BaseModel, EmailStr

from app.schemas.affiliate_account import AffiliateAccountOut
from app.schemas.tenant import TenantOut


class AffiliateRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    country: str
    state: str | None = None
    tax_status: str = "us_person"
    tax_form_type: str | None = None
    paypal_email: str | None = None


class AffiliateLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    token: str
    account: AffiliateAccountOut
    tenants: list[TenantOut]
