from pydantic import BaseModel, EmailStr

from app.schemas.affiliate_account import AffiliateAccountOut
from app.schemas.tenant import TenantOut
from app.schemas.tenant_user import TenantUserOut


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


class TenantLogin(BaseModel):
    email: EmailStr
    password: str


class AffiliateAcceptInvite(BaseModel):
    token: str
    email: EmailStr
    password: str | None = None
    name: str | None = None
    country: str | None = None
    state: str | None = None
    tax_status: str = "us_person"
    tax_form_type: str | None = None
    paypal_email: str | None = None


class AuthResponse(BaseModel):
    token: str
    account: AffiliateAccountOut
    tenants: list[TenantOut]


class TenantRegister(BaseModel):
    tenant_name: str
    email: EmailStr
    password: str
    admin_name: str | None = None


class TenantRegisterResponse(BaseModel):
    token: str
    tenant: TenantOut
    user: TenantUserOut
    api_key: str
