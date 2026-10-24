"""Pydantic schemas for Optimization APIs."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.models.scenario import OptimizationMode


# ── Feasibility Preview ─────────────────────────────────────────────────────


class FeasibilityRequest(BaseModel):
    scenario_id: uuid.UUID


class FeasibleVehicle(BaseModel):
    vehicle_id: uuid.UUID
    vehicle_name: str
    is_feasible: bool
    reasons: list[str]
    total_volume_kg: float
    remaining_capacity_kg: float


class ConsolidationOption(BaseModel):
    harvest_ids: list[uuid.UUID]
    is_feasible: bool
    reasons: list[str]
    total_volume_kg: float
    estimated_distance_km: float
    vehicle_id: uuid.UUID | None = None
    vehicle_name: str | None = None


class FeasibilityPreviewResponse(BaseModel):
    scenario_id: uuid.UUID
    feasible_vehicles: list[FeasibleVehicle]
    rejected_vehicles: list[FeasibleVehicle]
    consolidation_options: list[ConsolidationOption]


# ── Run Optimization ────────────────────────────────────────────────────────


class OptimizeRequest(BaseModel):
    scenario_id: uuid.UUID
    mode: OptimizationMode = OptimizationMode.BALANCED
    vehicle_id: uuid.UUID | None = Field(
        default=None,
        description="Required preferred vehicle; must be in the feasible set for this scenario",
    )


class RouteResultSchema(BaseModel):
    run_id: str
    result_type: Literal["baseline", "spoilage_aware"]
    mode: str
    vehicle_id: str
    pickup_sequence: list[str]
    distance_km: float
    duration_hours: float
    risk_score: float
    cost_idr: float
    geometry: str


class OptimizationResponse(BaseModel):
    scenario_id: uuid.UUID
    run_id: uuid.UUID | None = None
    mode: OptimizationMode
    baseline_route: RouteResultSchema
    spoilage_aware_route: RouteResultSchema
    # Economic impact
    estimated_food_loss_avoided_kg: float = 0.0
    economic_loss_avoided_idr: float = 0.0
    additional_logistics_cost_idr: float = 0.0
    net_value_idr: float = 0.0


class OptimizationRunSummary(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    scenario_name: str | None = None
    created_at: str
    formula_version: str
    alpha: float
    beta: float
    gamma: float
    food_loss_avoided_kg: float
    economic_loss_avoided_idr: float
    additional_logistics_cost_idr: float
    net_value_idr: float


class OptimizationRunDetail(OptimizationRunSummary):
    baseline_route: RouteResultSchema | None = None
    spoilage_aware_route: RouteResultSchema | None = None
