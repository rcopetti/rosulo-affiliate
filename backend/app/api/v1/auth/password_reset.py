from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.schemas.auth import (
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetVerify,
    PasswordResetVerifyResponse,
)
from app.services import email as email_service
from app.services import password_reset as reset_service

router = APIRouter()


@router.post("/request")
async def request_reset(data: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    code = await reset_service.request_code(db, data.email, data.user_type)
    if code is not None:
        await email_service.send_password_reset_code(data.email, code)
    return {"status": "ok"}


@router.post("/verify", response_model=PasswordResetVerifyResponse)
async def verify_reset(data: PasswordResetVerify, db: AsyncSession = Depends(get_db)):
    try:
        token = await reset_service.verify_code(db, data.email, data.user_type, data.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"reset_token": token}


@router.post("/confirm")
async def confirm_reset(data: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    try:
        await reset_service.confirm_reset(
            db, data.email, data.user_type, data.reset_token, data.new_password
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}
