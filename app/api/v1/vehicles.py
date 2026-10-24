"""Vehicle API endpoints — org-scoped."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal
from app.core.database import get_db
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("", response_model=list[VehicleResponse], summary="List available vehicles")
async def list_vehicles(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[VehicleResponse]:
    query = (
        select(Vehicle)
        .where(Vehicle.organization_id == principal.org_id)
        .order_by(Vehicle.capacity_kg)
    )
    if active_only:
        query = query.where(Vehicle.active.is_(True))
    result = await db.execute(query)
    return [VehicleResponse.model_validate(v) for v in result.scalars().all()]


@router.get("/{vehicle_id}", response_model=VehicleResponse, summary="Get a vehicle")
async def get_vehicle(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> VehicleResponse:
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.organization_id == principal.org_id,
        )
    )
    vehicle = result.scalar_one_or_none()
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return VehicleResponse.model_validate(vehicle)


@router.post(
    "",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a vehicle",
)
async def create_vehicle(
    payload: VehicleCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> VehicleResponse:
    if principal.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guests cannot create vehicles",
        )
    vehicle = Vehicle(**payload.model_dump(), organization_id=principal.org_id)
    db.add(vehicle)
    await db.flush()
    await db.refresh(vehicle)
    return VehicleResponse.model_validate(vehicle)


@router.patch("/{vehicle_id}", response_model=VehicleResponse, summary="Update a vehicle")
async def update_vehicle(
    vehicle_id: uuid.UUID,
    payload: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> VehicleResponse:
    if principal.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guests cannot update vehicles",
        )
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.organization_id == principal.org_id,
        )
    )
    vehicle = result.scalar_one_or_none()
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    await db.flush()
    await db.refresh(vehicle)
    return VehicleResponse.model_validate(vehicle)
