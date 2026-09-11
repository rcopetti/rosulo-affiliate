import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contract, Term


async def get_contract_for_affiliate(db: AsyncSession, affiliate_id: uuid.UUID):
    result = await db.execute(
        select(Contract).where(Contract.affiliate_id == affiliate_id, Contract.active == True)
    )
    return result.scalar_one_or_none()


async def get_contract(db: AsyncSession, contract_id: uuid.UUID):
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    return result.scalar_one_or_none()


async def add_term(db: AsyncSession, contract_id: uuid.UUID, data: dict) -> Term:
    contract = await get_contract(db, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    term = Term(
        contract_id=contract_id,
        payment_sequence=data.get("payment_sequence"),
        sequence_pattern=data.get("sequence_pattern", "*"),
        commission_percent=data["commission_percent"],
        minimum_threshold=data.get("minimum_threshold"),
        effective_from=data.get("effective_from") or date.today(),
        effective_to=data.get("effective_to"),
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


async def update_term(db: AsyncSession, term_id: uuid.UUID, data: dict) -> Term | None:
    result = await db.execute(select(Term).where(Term.id == term_id))
    term = result.scalar_one_or_none()
    if not term:
        return None
    for key, value in data.items():
        if value is not None and hasattr(term, key):
            setattr(term, key, value)
    await db.commit()
    await db.refresh(term)
    return term
