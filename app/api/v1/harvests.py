"""Harvest API endpoints — org / guest scoped."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import Principal, get_current_principal
from app.core.database import get_db
from app.core.tenancy import get_org_scenario
from app.models.commodity import Commodity
from app.models.harvest import Harvest
from app.models.scenario import ScenarioStatus
from app.schemas.harvest import HarvestCreate, HarvestResponse, HarvestUpdate

router = APIRouter(tags=["Harvests"])


def _harvest_to_response(harvest: Harvest) -> HarvestResponse:
    return HarvestResponse(
        id=harvest.id,
        scenario_id=harvest.scenario_id,
        commodity_id=harvest.commodity_id,
        label=harvest.label,
        location_lat=harvest.location_lat,
        location_lng=harvest.location_lng,
        volume_kg=harvest.volume_kg,
        harvested_at=harvest.harvested_at,
        destination_lat=harvest.destination_lat,
        destination_lng=harvest.destination_lng,
        destination_name=harvest.destination_name,
        handling_factor=harvest.handling_factor,
        created_at=harvest.created_at,
        commodity_name=harvest.commodity.name if harvest.commodity else None,
        perishability_class=(
            harvest.commodity.perishability_class if harvest.commodity else None
        ),
        shelf_life_hours=(
            harvest.commodity.shelf_life_hours if harvest.commodity else None
        ),
    )


@router.post(
    "/scenarios/{scenario_id}/harvests",
    response_model=HarvestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_harvest(
    scenario_id: uuid.UUID,
    payload: HarvestCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> HarvestResponse:
    scenario = await get_org_scenario(db, scenario_id, principal)
    if scenario.status != ScenarioStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot add harvests to scenario in '{scenario.status.value}' status. "
                "POST /scenarios/{id}/reset-to-draft first."
            ),
        )

    result = await db.execute(
        select(Commodity).where(
            Commodity.id == payload.commodity_id,
            Commodity.organization_id == principal.org_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commodity not found")

    harvest = Harvest(scenario_id=scenario_id, **payload.model_dump())
    db.add(harvest)
    await db.flush()
    await db.refresh(harvest, ["commodity"])
    return _harvest_to_response(harvest)


@router.get("/scenarios/{scenario_id}/harvests", response_model=list[HarvestResponse])
async def list_harvests(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[HarvestResponse]:
    await get_org_scenario(db, scenario_id, principal)
    result = await db.execute(
        select(Harvest)
        .where(Harvest.scenario_id == scenario_id)
        .options(selectinload(Harvest.commodity))
        .order_by(Harvest.label)
    )
    return [_harvest_to_response(h) for h in result.scalars().all()]


@router.patch("/harvests/{harvest_id}", response_model=HarvestResponse)
async def update_harvest(
    harvest_id: uuid.UUID,
    payload: HarvestUpdate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> HarvestResponse:
    result = await db.execute(
        select(Harvest)
        .where(Harvest.id == harvest_id)
        .options(selectinload(Harvest.scenario), selectinload(Harvest.commodity))
    )
    harvest = result.scalar_one_or_none()
    if harvest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Harvest not found")
    await get_org_scenario(db, harvest.scenario_id, principal)

    update_data = payload.model_dump(exclude_unset=True)
    if "commodity_id" in update_data:
        c_result = await db.execute(
            select(Commodity).where(
                Commodity.id == update_data["commodity_id"],
                Commodity.organization_id == principal.org_id,
            )
        )
        if c_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commodity not found")

    for field, value in update_data.items():
        setattr(harvest, field, value)
    await db.flush()
    await db.refresh(harvest, ["commodity"])
    return _harvest_to_response(harvest)


@router.delete("/harvests/{harvest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_harvest(
    harvest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> None:
    result = await db.execute(select(Harvest).where(Harvest.id == harvest_id))
    harvest = result.scalar_one_or_none()
    if harvest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Harvest not found")
    await get_org_scenario(db, harvest.scenario_id, principal)
    await db.delete(harvest)
