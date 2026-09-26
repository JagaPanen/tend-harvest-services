"""Scenario API endpoints.

POST /api/v1/scenarios — Create a planning scenario
GET  /api/v1/scenarios — List all scenarios
GET  /api/v1/scenarios/{id} — Get scenario details with harvests
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.harvest import Harvest
from app.models.scenario import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioDetailResponse, ScenarioResponse, ScenarioUpdate

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


def _scenario_to_response(scenario: Scenario, harvest_count: int = 0) -> ScenarioResponse:
    """Convert a Scenario ORM object to a response schema."""
    return ScenarioResponse(
        id=scenario.id,
        name=scenario.name,
        status=scenario.status,
        optimization_mode=scenario.optimization_mode,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
        harvest_count=harvest_count,
    )


@router.post(
    "",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a planning scenario",
)
async def create_scenario(
    payload: ScenarioCreate,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    """Create a new planning scenario."""
    scenario = Scenario(**payload.model_dump())
    db.add(scenario)
    await db.flush()
    await db.refresh(scenario)
    return _scenario_to_response(scenario, harvest_count=0)


@router.get(
    "",
    response_model=list[ScenarioResponse],
    summary="List all scenarios",
)
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
) -> list[ScenarioResponse]:
    """List all planning scenarios with harvest counts."""
    # Subquery for harvest count
    harvest_count_sq = (
        select(Harvest.scenario_id, func.count(Harvest.id).label("count"))
        .group_by(Harvest.scenario_id)
        .subquery()
    )

    query = (
        select(Scenario, func.coalesce(harvest_count_sq.c.count, 0).label("harvest_count"))
        .outerjoin(harvest_count_sq, Scenario.id == harvest_count_sq.c.scenario_id)
        .order_by(Scenario.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.all()
    return [_scenario_to_response(row[0], harvest_count=row[1]) for row in rows]


@router.get(
    "/{scenario_id}",
    response_model=ScenarioDetailResponse,
    summary="Get scenario details",
)
async def get_scenario(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScenarioDetailResponse:
    """Retrieve a scenario with its harvests and commodity details."""
    result = await db.execute(
        select(Scenario)
        .where(Scenario.id == scenario_id)
        .options(selectinload(Scenario.harvests))
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    # Build harvest responses with commodity info
    from app.schemas.harvest import HarvestResponse

    harvest_responses = []
    for h in scenario.harvests:
        hr = HarvestResponse(
            id=h.id,
            scenario_id=h.scenario_id,
            commodity_id=h.commodity_id,
            label=h.label,
            location_lat=h.location_lat,
            location_lng=h.location_lng,
            volume_kg=h.volume_kg,
            harvested_at=h.harvested_at,
            destination_lat=h.destination_lat,
            destination_lng=h.destination_lng,
            destination_name=h.destination_name,
            handling_factor=h.handling_factor,
            created_at=h.created_at,
            commodity_name=h.commodity.name if h.commodity else None,
            perishability_class=h.commodity.perishability_class if h.commodity else None,
            shelf_life_hours=h.commodity.shelf_life_hours if h.commodity else None,
        )
        harvest_responses.append(hr)

    return ScenarioDetailResponse(
        id=scenario.id,
        name=scenario.name,
        status=scenario.status,
        optimization_mode=scenario.optimization_mode,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
        harvest_count=len(harvest_responses),
        harvests=harvest_responses,
    )


@router.patch(
    "/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Update a scenario",
)
async def update_scenario(
    scenario_id: uuid.UUID,
    payload: ScenarioUpdate,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    """Update an existing scenario's fields."""
    result = await db.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scenario, field, value)

    await db.flush()
    await db.refresh(scenario)

    # Count harvests
    count_result = await db.execute(
        select(func.count(Harvest.id)).where(Harvest.scenario_id == scenario_id)
    )
    harvest_count = count_result.scalar() or 0

    return _scenario_to_response(scenario, harvest_count=harvest_count)


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scenario",
)
async def delete_scenario(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a scenario and all its harvests."""
    result = await db.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    await db.delete(scenario)
