import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.db.dependencies import get_db
from app.db.models import Tenant
from app.schemas.contract import ContractOut, ContractUpdate, TermCreate, TermOut, TermUpdate
from app.services import contract as contract_service
from app.services import affiliate as affiliate_service

router = APIRouter()


@router.get("/{affiliate_id}/contract", response_model=ContractOut)
async def get_contract(
    affiliate_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    affiliate = await affiliate_service.get_affiliate(db, uuid.UUID(affiliate_id), tenant)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    contract = await contract_service.get_contract_for_affiliate(db, affiliate["id"])
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@router.put("/{affiliate_id}/contract", response_model=ContractOut)
async def update_contract(
    affiliate_id: str,
    update: ContractUpdate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    affiliate = await affiliate_service.get_affiliate(db, uuid.UUID(affiliate_id), tenant)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    contract = await contract_service.get_contract_for_affiliate(db, affiliate["id"])
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    update_data = update.model_dump(exclude_unset=True, exclude={"terms"})
    for key, value in update_data.items():
        setattr(contract, key, value)
    if update.terms is not None:
        await contract_service.sync_terms(db, contract, update.terms)
    await db.commit()
    await db.refresh(contract)
    return contract


@router.post("/{affiliate_id}/contract/terms", response_model=TermOut)
async def add_term(
    affiliate_id: str,
    data: TermCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    affiliate = await affiliate_service.get_affiliate(db, uuid.UUID(affiliate_id), tenant)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    contract = await contract_service.get_contract_for_affiliate(db, affiliate["id"])
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return await contract_service.add_term(db, contract.id, data.model_dump())


@router.patch("/{affiliate_id}/contract/terms/{term_id}", response_model=TermOut)
async def update_term(
    affiliate_id: str,
    term_id: str,
    data: TermUpdate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    affiliate = await affiliate_service.get_affiliate(db, uuid.UUID(affiliate_id), tenant)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    return await contract_service.update_term(db, uuid.UUID(term_id), data.model_dump())
