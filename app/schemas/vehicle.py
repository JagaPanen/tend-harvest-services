"""Pydantic schemas for the Vehicle entity."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VehicleBase(BaseModel):
    """Shared vehicle fields."""

    name: str = Field(..., max_length=100, examples=["Pickup Truck 500kg"])
    capacity_kg: float = Field(..., gt=0, description="Maximum load capacity in kg", examples=[500.0])
    current_location_lat: float = Field(
        ..., ge=-90, le=90, description="Current latitude", examples=[-6.9175]
    )
    current_location_lng: float = Field(
        ..., ge=-180, le=180, description="Current longitude", examples=[107.6191]
    )
    available_from: datetime = Field(..., description="Earliest availability time")
    available_until: datetime | None = Field(
        default=None, description="Latest availability time (null = no limit)"
    )
    cost_per_km_idr: float = Field(
        ..., gt=0, description="Operating cost per km in IDR", examples=[5000.0]
    )


class VehicleCreate(VehicleBase):
    """Schema for creating a new vehicle."""

    pass


class VehicleUpdate(BaseModel):
    """Schema for updating an existing vehicle (all fields optional)."""

    name: str | None = Field(default=None, max_length=100)
    capacity_kg: float | None = Field(default=None, gt=0)
    current_location_lat: float | None = Field(default=None, ge=-90, le=90)
    current_location_lng: float | None = Field(default=None, ge=-180, le=180)
    available_from: datetime | None = None
    available_until: datetime | None = None
    cost_per_km_idr: float | None = Field(default=None, gt=0)
    active: bool | None = None


class VehicleResponse(VehicleBase):
    """Schema for vehicle API response."""

    id: uuid.UUID
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
