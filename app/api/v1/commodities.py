"""Commodity API endpoints.

GET /api/v1/commodities — List all active commodities with their perishability
classifications, shelf life references, and default prices.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.commodity import Commodity
from app.schemas.commodity import CommodityCreate, CommodityResponse, CommodityUpdate

router = APIRouter(prefix="/commodities", tags=["Commodities"])


@router.get(
    "",
    response_model=list[CommodityResponse],
    summary="List commodity classes",
    description="Retrieve all active commodity types with their perishability class, shelf life, and default prices.",
)
async def list_commodities(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
) -> list[CommodityResponse]:
    """List all commodities, optionally filtering by active status."""
    query = select(Commodity).order_by(Commodity.perishability_class)
    if active_only:
        query = query.where(Commodity.active.is_(True))

    result = await db.execute(query)
    commodities = result.scalars().all()
    return [CommodityResponse.model_validate(c) for c in commodities]


@router.get(
    "/{commodity_id}",
    response_model=CommodityResponse,
    summary="Get a commodity",
)
async def get_commodity(
    commodity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CommodityResponse:
    """Retrieve a single commodity by ID."""
    result = await db.execute(select(Commodity).where(Commodity.id == commodity_id))
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
) -> CommodityResponse:
    """Create a new commodity type."""
    commodity = Commodity(**payload.model_dump())
    db.add(commodity)
    await db.flush()
    await db.refresh(commodity)
    return CommodityResponse.model_validate(commodity)


@router.patch(
    "/{commodity_id}",
    response_model=CommodityResponse,
    summary="Update a commodity",
)
async def update_commodity(
    commodity_id: uuid.UUID,
    payload: CommodityUpdate,
    db: AsyncSession = Depends(get_db),
) -> CommodityResponse:
    """Update an existing commodity's fields."""
    result = await db.execute(select(Commodity).where(Commodity.id == commodity_id))
    commodity = result.scalar_one_or_none()
    if commodity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commodity not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(commodity, field, value)

    await db.flush()
    await db.refresh(commodity)
    return CommodityResponse.model_validate(commodity)
