import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contract, Term
from app.schemas.contract import TermCreate


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


async def sync_terms(db: AsyncSession, contract: Contract, terms_data: list[TermCreate]) -> None:
    """Replace the contract's terms with the given list.

    Existing terms are matched by id and updated in place; terms absent from
    the payload are removed; terms without an id are created.
    """
    result = await db.execute(select(Term).where(Term.contract_id == contract.id))
    existing = {str(t.id): t for t in result.scalars().all()}

    seen: set[str] = set()
    for term_data in terms_data:
        term_id = None
        raw_id = (term_data.id or "").strip()
        if raw_id:
            try:
                term_id = str(uuid.UUID(raw_id))
            except ValueError:
                term_id = None
        if term_id and term_id in existing:
            term = existing[term_id]
            term.payment_sequence = term_data.payment_sequence
            term.sequence_pattern = term_data.sequence_pattern
            term.commission_percent = term_data.commission_percent
            term.minimum_threshold = term_data.minimum_threshold
            if term_data.effective_from is not None:
                term.effective_from = term_data.effective_from
            if term_data.effective_to is not None:
                term.effective_to = term_data.effective_to
            seen.add(term_id)
        else:
            db.add(
                Term(
                    contract_id=contract.id,
                    payment_sequence=term_data.payment_sequence,
                    sequence_pattern=term_data.sequence_pattern,
                    commission_percent=term_data.commission_percent,
                    minimum_threshold=term_data.minimum_threshold,
                    effective_from=term_data.effective_from or date.today(),
                    effective_to=term_data.effective_to,
                )
            )

    for term_id, term in existing.items():
        if term_id not in seen:
            await db.delete(term)
