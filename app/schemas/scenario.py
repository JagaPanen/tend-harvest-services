"""Pydantic schemas for the Scenario entity."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.scenario import OptimizationMode, ScenarioStatus


class ScenarioCreate(BaseModel):
    """Schema for creating a new planning scenario."""

    name: str = Field(
        ..., max_length=200, examples=["Bandung Morning Harvest — Sep 27"]
    )
    optimization_mode: OptimizationMode = Field(
        default=OptimizationMode.BALANCED,
        description="Optimization mode: cost_priority, balanced, or spoilage_priority",
    )


class ScenarioUpdate(BaseModel):
    """Schema for updating an existing scenario."""

    name: str | None = Field(default=None, max_length=200)
    optimization_mode: OptimizationMode | None = None
    status: ScenarioStatus | None = None


class ScenarioResponse(BaseModel):
    """Schema for scenario API response."""

    id: uuid.UUID
    name: str
    status: ScenarioStatus
    optimization_mode: OptimizationMode
    created_at: datetime
    updated_at: datetime
    harvest_count: int = Field(default=0, description="Number of harvests in this scenario")

    model_config = {"from_attributes": True}


class ScenarioDetailResponse(ScenarioResponse):
    """Scenario with nested harvest details."""

    from app.schemas.harvest import HarvestResponse

    harvests: list[HarvestResponse] = []
