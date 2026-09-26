"""Pydantic schemas for the Commodity entity."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CommodityBase(BaseModel):
    """Shared commodity fields."""

    name: str = Field(..., max_length=100, examples=["Tomato"])
    perishability_class: str = Field(
        ...,
        min_length=1,
        max_length=1,
        pattern=r"^[A-E]$",
        description="A (most perishable) to E (least perishable)",
        examples=["A"],
    )
    shelf_life_hours: float = Field(
        ..., gt=0, description="Estimated shelf life under standard conditions (hours)", examples=[18.0]
    )
    default_price_idr_per_kg: float = Field(
        ..., gt=0, description="Default commodity price in IDR per kg", examples=[15000.0]
    )


class CommodityCreate(CommodityBase):
    """Schema for creating a new commodity."""

    pass


class CommodityUpdate(BaseModel):
    """Schema for updating an existing commodity (all fields optional)."""

    name: str | None = Field(default=None, max_length=100)
    perishability_class: str | None = Field(default=None, pattern=r"^[A-E]$")
    shelf_life_hours: float | None = Field(default=None, gt=0)
    default_price_idr_per_kg: float | None = Field(default=None, gt=0)
    active: bool | None = None


class CommodityResponse(CommodityBase):
    """Schema for commodity API response."""

    id: uuid.UUID
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
