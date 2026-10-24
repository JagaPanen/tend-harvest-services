"""Commodity API endpoints — org-scoped."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal
from app.core.database import get_db
from app.models.commodity import Commodity
from app.schemas.commodity import CommodityCreate, CommodityResponse, CommodityUpdate

router = APIRouter(prefix="/commodities", tags=["Commodities"])


@router.get("", response_model=list[CommodityResponse], summary="List commodity classes")
async def list_commodities(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[CommodityResponse]:
    query = (
        select(Commodity)
        .where(Commodity.organization_id == principal.org_id)
        .order_by(Commodity.perishability_class)
    )
    if active_only:
        query = query.where(Commodity.active.is_(True))
    result = await db.execute(query)
    return [CommodityResponse.model_validate(c) for c in result.scalars().all()]


@router.get("/{commodity_id}", response_model=CommodityResponse, summary="Get a commodity")
async def get_commodity(
    commodity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> CommodityResponse:
    result = await db.execute(
        select(Commodity).where(
            Commodity.id == commodity_id,
            Commodity.organization_id == principal.org_id,
        )
    )
    commodity = result.scalar_one_or_none()
    if commodity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commodity not found")
    return CommodityResponse.model_validate(commodity)


@router.post(
    "",
    response_model=CommodityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a commodity",
)
async def create_commodity(
    payload: CommodityCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> CommodityResponse:
    if principal.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guests cannot create commodities",
        )
    commodity = Commodity(**payload.model_dump(), organization_id=principal.org_id)
    db.add(commodity)
    await db.flush()
    await db.refresh(commodity)
    return CommodityResponse.model_validate(commodity)


@router.patch("/{commodity_id}", response_model=CommodityResponse, summary="Update a commodity")
async def update_commodity(
    commodity_id: uuid.UUID,
    payload: CommodityUpdate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> CommodityResponse:
    if principal.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guests cannot update commodities",
        )
    result = await db.execute(
        select(Commodity).where(
            Commodity.id == commodity_id,
            Commodity.organization_id == principal.org_id,
        )
    )
    commodity = result.scalar_one_or_none()
    if commodity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commodity not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(commodity, field, value)
    await db.flush()
    await db.refresh(commodity)
    return CommodityResponse.model_validate(commodity)
