"""Pydantic schemas for the Risk Scoring API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────

class RiskScoreHarvestInput(BaseModel):
    """Inline harvest data for risk scoring (when harvest isn't persisted yet)."""

    label: str = Field(..., max_length=50, examples=["A"])
    commodity_id: uuid.UUID = Field(..., description="ID of the commodity type")
    harvested_at: datetime = Field(..., description="Actual harvest timestamp")
    estimated_transit_hours: float = Field(
        default=0.0, ge=0, description="Estimated transit time in hours", examples=[6.0]
    )
    handling_factor: float = Field(
        default=1.0, ge=1.0, description="Handling multiplier", examples=[1.0]
    )


class RiskScoreRequest(BaseModel):
    """Request body for POST /api/v1/risk/score.

    Provide *either* ``harvest_ids`` (to score persisted harvests) or
    ``harvests`` (to score inline data). If both are provided, they are
    merged.
    """

    harvest_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Score persisted harvests by their IDs",
    )
    harvests: list[RiskScoreHarvestInput] | None = Field(
        default=None,
        description="Score inline harvest data (no database lookup needed)",
    )
    estimated_transit_hours: float = Field(
        default=0.0,
        ge=0,
        description="Default transit hours applied to harvest_ids (overridden by per-harvest values)",
    )
    reference_time: datetime | None = Field(
        default=None,
        description="Override 'now' for testing or what-if analysis",
    )


# ── Response schemas ─────────────────────────────────────────────────────────

class RiskScoreItemResponse(BaseModel):
    """Risk score result for a single harvest."""

    harvest_id: str = Field(..., description="Harvest ID or inline label")
    label: str
    perishability_class: str = Field(..., description="A–E")
    urgency_score: float = Field(..., ge=0, le=100, description="0–100, higher = more urgent")
    recommended_max_transit_hours: float = Field(
        ..., ge=0, description="Hours of transit remaining before score hits 80"
    )
    priority_level: str = Field(..., description="critical / high / medium / low")
    time_since_harvest_hours: float
    estimated_transit_hours: float
    shelf_life_hours: float
    handling_factor: float
    formula_version: str
    explanation: str


class RiskScoreResponse(BaseModel):
    """Response for POST /api/v1/risk/score."""

    count: int = Field(..., description="Number of harvests scored")
    formula_version: str
    results: list[RiskScoreItemResponse]
