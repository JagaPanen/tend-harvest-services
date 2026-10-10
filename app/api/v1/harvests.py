"""Harvest API endpoints.

POST /api/v1/scenarios/{id}/harvests — Add a harvest to a scenario
GET  /api/v1/scenarios/{id}/harvests — List harvests in a scenario
PATCH /api/v1/harvests/{id} — Update a harvest
DELETE /api/v1/harvests/{id} — Delete a harvest
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.commodity import Commodity
from app.models.harvest import Harvest
from app.models.scenario import Scenario, ScenarioStatus
from app.schemas.harvest import HarvestCreate, HarvestResponse, HarvestUpdate

router = APIRouter(tags=["Harvests"])


def _harvest_to_response(harvest: Harvest) -> HarvestResponse:
    """Convert a Harvest ORM object to a response schema."""
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
        perishability_class=harvest.commodity.perishability_class if harvest.commodity else None,
        shelf_life_hours=harvest.commodity.shelf_life_hours if harvest.commodity else None,
    )


@router.post(
    "/scenarios/{scenario_id}/harvests",
    response_model=HarvestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a harvest to a scenario",
)
async def add_harvest(
    scenario_id: uuid.UUID,
    payload: HarvestCreate,
    db: AsyncSession = Depends(get_db),
) -> HarvestResponse:
    """Add a new harvest input to an existing scenario."""
    # Validate scenario exists and is in draft status
    result = await db.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    if scenario.status != ScenarioStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add harvests to scenario in '{scenario.status.value}' status",
        )

    # Validate commodity exists
    result = await db.execute(select(Commodity).where(Commodity.id == payload.commodity_id))
    commodity = result.scalar_one_or_none()
    if commodity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commodity not found")

    harvest = Harvest(scenario_id=scenario_id, **payload.model_dump())
    db.add(harvest)
    await db.flush()
    await db.refresh(harvest, ["commodity"])

    return _harvest_to_response(harvest)


@router.get(
    "/scenarios/{scenario_id}/harvests",
    response_model=list[HarvestResponse],
    summary="List harvests in a scenario",
)
async def list_harvests(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[HarvestResponse]:
    """List all harvest inputs in a scenario."""
    # Validate scenario exists
    result = await db.execute(select(Scenario).where(Scenario.id == scenario_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    result = await db.execute(
        select(Harvest)
        .where(Harvest.scenario_id == scenario_id)
        .options(selectinload(Harvest.commodity))
        .order_by(Harvest.label)
    )
    harvests = result.scalars().all()
    return [_harvest_to_response(h) for h in harvests]


@router.patch(
    "/harvests/{harvest_id}",
    response_model=HarvestResponse,
    summary="Update a harvest",
)
async def update_harvest(
    harvest_id: uuid.UUID,
    payload: HarvestUpdate,
    db: AsyncSession = Depends(get_db),
) -> HarvestResponse:
    """Update an existing harvest's fields."""
    result = await db.execute(select(Harvest).where(Harvest.id == harvest_id))
    harvest = result.scalar_one_or_none()
    if harvest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Harvest not found")

    update_data = payload.model_dump(exclude_unset=True)

    # If commodity_id is being changed, validate it
    if "commodity_id" in update_data:
        result = await db.execute(
            select(Commodity).where(Commodity.id == update_data["commodity_id"])
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Commodity not found"
            )

    for field, value in update_data.items():
        setattr(harvest, field, value)

    await db.flush()
    await db.refresh(harvest, ["commodity"])
    return _harvest_to_response(harvest)


@router.delete(
    "/harvests/{harvest_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a harvest",
)
async def delete_harvest(
    harvest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a harvest from its scenario."""
    result = await db.execute(select(Harvest).where(Harvest.id == harvest_id))
    harvest = result.scalar_one_or_none()
    if harvest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Harvest not found")

    await db.delete(harvest)
