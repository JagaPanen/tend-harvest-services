"""Pydantic schemas for the Harvest entity."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class HarvestBase(BaseModel):
    """Shared harvest fields."""

    commodity_id: uuid.UUID = Field(..., description="ID of the commodity type")
    label: str = Field(
        ..., max_length=50, description="Short label (e.g. 'A', 'B')", examples=["A"]
    )
    location_lat: float = Field(..., ge=-90, le=90, description="Harvest latitude", examples=[-6.85])
    location_lng: float = Field(
        ..., ge=-180, le=180, description="Harvest longitude", examples=[107.55]
    )
    volume_kg: float = Field(..., gt=0, description="Harvest volume in kg", examples=[300.0])
    harvested_at: datetime = Field(..., description="Actual harvest timestamp")
    destination_lat: float = Field(
        ..., ge=-90, le=90, description="Delivery destination latitude", examples=[-6.92]
    )
    destination_lng: float = Field(
        ..., ge=-180, le=180, description="Delivery destination longitude", examples=[107.61]
    )
    destination_name: str = Field(
        default="Destination",
        max_length=200,
        description="Human-readable destination name",
        examples=["Pasar Induk Caringin"],
    )
    handling_factor: float = Field(
        default=1.0,
        ge=1.0,
        description="Handling multiplier: 1.0 = standard, >1.0 = suboptimal",
        examples=[1.0],
    )


class HarvestCreate(HarvestBase):
    """Schema for creating a new harvest input."""

    pass


class HarvestUpdate(BaseModel):
    """Schema for updating an existing harvest (all fields optional)."""

    commodity_id: uuid.UUID | None = None
    label: str | None = Field(default=None, max_length=50)
    location_lat: float | None = Field(default=None, ge=-90, le=90)
    location_lng: float | None = Field(default=None, ge=-180, le=180)
    volume_kg: float | None = Field(default=None, gt=0)
    harvested_at: datetime | None = None
    destination_lat: float | None = Field(default=None, ge=-90, le=90)
    destination_lng: float | None = Field(default=None, ge=-180, le=180)
    destination_name: str | None = Field(default=None, max_length=200)
    handling_factor: float | None = Field(default=None, ge=1.0)


class HarvestResponse(HarvestBase):
    """Schema for harvest API response."""

    id: uuid.UUID
    scenario_id: uuid.UUID
    created_at: datetime

    # Include commodity details inline for convenience
    commodity_name: str | None = None
    perishability_class: str | None = None
    shelf_life_hours: float | None = None

    model_config = {"from_attributes": True}
