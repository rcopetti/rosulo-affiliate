from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.schemas.auth import AffiliateLogin, AffiliateRegister, Token
from app.services import affiliate_account as acct_service

router = APIRouter()


@router.post("/affiliate/register", response_model=Token)
async def register(data: AffiliateRegister, db: AsyncSession = Depends(get_db)):
    account = await acct_service.register_account(db, data)
    token = await acct_service.authenticate_account(
        db, AffiliateLogin(email=data.email, password=data.password)
    )
    return Token(access_token=token)


@router.post("/affiliate/login", response_model=Token)
async def login(data: AffiliateLogin, db: AsyncSession = Depends(get_db)):
    token = await acct_service.authenticate_account(db, data)
    return Token(access_token=token)
