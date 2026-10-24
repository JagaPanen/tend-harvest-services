"""Scenario API endpoints — org / guest scoped."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import Principal, get_current_principal
from app.core.database import get_db
from app.core.tenancy import apply_scenario_visibility, get_org_scenario
from app.models.harvest import Harvest
from app.models.scenario import Scenario, ScenarioStatus
from app.schemas.scenario import ScenarioCreate, ScenarioDetailResponse, ScenarioResponse, ScenarioUpdate

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


def _scenario_to_response(scenario: Scenario, harvest_count: int = 0) -> ScenarioResponse:
    return ScenarioResponse(
        id=scenario.id,
        name=scenario.name,
        status=scenario.status,
        optimization_mode=scenario.optimization_mode,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
        harvest_count=harvest_count,
    )


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    payload: ScenarioCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ScenarioResponse:
    if principal.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guests use the cloned demo scenario; create an account for new scenarios",
        )
    scenario = Scenario(
        **payload.model_dump(),
        organization_id=principal.org_id,
        is_template=False,
        guest_session_id=None,
    )
    db.add(scenario)
    await db.flush()
    await db.refresh(scenario)
    return _scenario_to_response(scenario, harvest_count=0)


@router.get("", response_model=list[ScenarioResponse])
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[ScenarioResponse]:
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
    query = apply_scenario_visibility(query, principal)
    # Guests should not list the template either (apply_scenario_visibility already filters)
    if not principal.is_guest:
        query = query.where(Scenario.is_template.is_(False))
    result = await db.execute(query)
    rows = result.all()
    return [_scenario_to_response(row[0], harvest_count=row[1]) for row in rows]


@router.get("/{scenario_id}", response_model=ScenarioDetailResponse)
async def get_scenario(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ScenarioDetailResponse:
    stmt = apply_scenario_visibility(
        select(Scenario)
        .where(Scenario.id == scenario_id)
        .options(selectinload(Scenario.harvests).selectinload(Harvest.commodity)),
        principal,
    )
    result = await db.execute(stmt)
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    from app.schemas.harvest import HarvestResponse

    harvest_responses = []
    for h in scenario.harvests:
        harvest_responses.append(
            HarvestResponse(
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
        )

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


@router.patch("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: uuid.UUID,
    payload: ScenarioUpdate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ScenarioResponse:
    scenario = await get_org_scenario(db, scenario_id, principal)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(scenario, field, value)
    await db.flush()
    await db.refresh(scenario)
    count_result = await db.execute(
        select(func.count(Harvest.id)).where(Harvest.scenario_id == scenario_id)
    )
    return _scenario_to_response(scenario, harvest_count=count_result.scalar() or 0)


@router.post(
    "/{scenario_id}/reset-to-draft",
    response_model=ScenarioResponse,
    summary="Reset scenario to draft so harvests can be edited again",
)
async def reset_scenario_to_draft(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ScenarioResponse:
    scenario = await get_org_scenario(db, scenario_id, principal)
    scenario.status = ScenarioStatus.DRAFT
    await db.flush()
    await db.refresh(scenario)
    count_result = await db.execute(
        select(func.count(Harvest.id)).where(Harvest.scenario_id == scenario_id)
    )
    return _scenario_to_response(scenario, harvest_count=count_result.scalar() or 0)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> None:
    scenario = await get_org_scenario(db, scenario_id, principal)
    if scenario.is_template:
        raise HTTPException(status_code=403, detail="Cannot delete the demo template")
    await db.delete(scenario)
