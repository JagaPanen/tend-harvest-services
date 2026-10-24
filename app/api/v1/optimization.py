"""Optimization API endpoints.

POST /api/v1/optimization/preview — Feasibility check
POST /api/v1/optimization/run — Generate routes
GET /api/v1/optimization/runs/{id} — Retrieve run
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import Principal, get_current_principal
from app.core.config import settings
from app.core.database import get_db
from app.core.tenancy import get_org_scenario
from app.models.commodity import Commodity
from app.models.harvest import Harvest
from app.models.optimization_run import OptimizationRun, RouteResultData, DecisionExplanation
from app.models.organization import DemoSession
from app.models.scenario import Scenario, ScenarioStatus
from app.models.vehicle import Vehicle

from app.schemas.optimization import (
    FeasibilityPreviewResponse,
    FeasibilityRequest,
    FeasibleVehicle,
    ConsolidationOption,
    OptimizeRequest,
    OptimizationResponse,
    RouteResultSchema,
)

from app.services.optimization.feasibility import (
    HarvestDemand,
    VehicleCandidate,
    filter_feasible_vehicles,
)
from app.services.optimization.consolidation import evaluate_consolidation
from app.services.optimization.optimizer import RouteOptimizer
from app.services.optimization.economic import calculate_impact
from app.services.risk.scorer import score_harvests, HarvestRiskInput, CommodityInfo
from app.services.routing.adapter import RoutingAdapter


router = APIRouter(prefix="/optimization", tags=["Optimization"])


async def _load_scenario_data(
    db: AsyncSession,
    scenario_id: uuid.UUID,
    principal: Principal,
):
    """Load scenario (org-scoped), harvests, and org vehicles."""
    await get_org_scenario(db, scenario_id, principal)
    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.harvests).selectinload(Harvest.commodity))
        .where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    v_result = await db.execute(
        select(Vehicle).where(
            Vehicle.active.is_(True),
            Vehicle.organization_id == principal.org_id,
        )
    )
    vehicles = v_result.scalars().all()
    return scenario, vehicles


async def _consume_guest_run(db: AsyncSession, principal: Principal) -> None:
    if not principal.is_guest:
        return
    if principal.session_id is None:
        raise HTTPException(status_code=401, detail="Guest session missing")
    demo = await db.get(DemoSession, principal.session_id)
    if demo is None:
        raise HTTPException(status_code=401, detail="Guest session not found")
    if demo.runs_used >= settings.guest_max_optimize_runs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Guest demo limit reached ({settings.guest_max_optimize_runs} runs). "
                "Sign up to continue."
            ),
        )
    demo.runs_used += 1


@router.post(
    "/preview",
    response_model=FeasibilityPreviewResponse,
    summary="Preview feasibility & consolidation",
)
async def preview_feasibility(
    payload: FeasibilityRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    scenario, db_vehicles = await _load_scenario_data(db, payload.scenario_id, principal)
    if not scenario.harvests:
        raise HTTPException(status_code=400, detail="Scenario has no harvests")

    # 1. Score harvests for urgency
    now = datetime.now(timezone.utc)
    risk_inputs = [
        HarvestRiskInput(
            harvest_id=str(h.id),
            label=h.label,
            commodity=CommodityInfo(
                perishability_class=h.commodity.perishability_class,
                shelf_life_hours=h.commodity.shelf_life_hours,
                default_price_idr_per_kg=h.commodity.default_price_idr_per_kg,
            ),
            harvested_at=h.harvested_at,
            handling_factor=h.handling_factor,
        ) for h in scenario.harvests
    ]
    risk_results = {r.harvest_id: r for r in score_harvests(risk_inputs, reference_time=now)}

    # 2. Build demands
    demands = [
        HarvestDemand(
            harvest_id=str(h.id),
            label=h.label,
            volume_kg=h.volume_kg,
            pickup_lat=h.location_lat,
            pickup_lng=h.location_lng,
            destination_lat=h.destination_lat,
            destination_lng=h.destination_lng,
            recommended_max_transit_hours=risk_results[str(h.id)].recommended_max_transit_hours,
        ) for h in scenario.harvests
    ]

    # 3. Build vehicle candidates
    candidates = [
        VehicleCandidate(
            vehicle_id=str(v.id),
            name=v.name,
            capacity_kg=v.capacity_kg,
            current_lat=v.current_location_lat,
            current_lng=v.current_location_lng,
            available_from=v.available_from,
            available_until=v.available_until,
            cost_per_km_idr=v.cost_per_km_idr,
        ) for v in db_vehicles
    ]

    # 4. Check feasibility
    feasible, rejected = filter_feasible_vehicles(candidates, demands, planned_departure=now)

    feasible_schemas = [
        FeasibleVehicle(
            vehicle_id=uuid.UUID(f.vehicle_id),
            vehicle_name=f.vehicle_name,
            is_feasible=True,
            reasons=f.reasons,
            total_volume_kg=f.total_demand_kg,
            remaining_capacity_kg=f.remaining_capacity_kg,
        ) for f in feasible
    ]
    rejected_schemas = [
        FeasibleVehicle(
            vehicle_id=uuid.UUID(r.vehicle_id),
            vehicle_name=r.vehicle_name,
            is_feasible=False,
            reasons=r.reasons,
            total_volume_kg=r.total_demand_kg,
            remaining_capacity_kg=r.remaining_capacity_kg,
        ) for r in rejected
    ]

    # 5. Consolidation options for each feasible vehicle (all harvests in one load)
    consolidations = []
    for f in feasible:
        candidate = next(c for c in candidates if c.vehicle_id == f.vehicle_id)
        consolidation = evaluate_consolidation(candidate, demands)
        consolidations.append(
            ConsolidationOption(
                harvest_ids=[uuid.UUID(hid) for hid in consolidation.harvest_ids],
                is_feasible=consolidation.is_feasible,
                reasons=consolidation.reasons,
                total_volume_kg=consolidation.total_volume_kg,
                estimated_distance_km=consolidation.estimated_distance_km,
                vehicle_id=uuid.UUID(f.vehicle_id),
                vehicle_name=f.vehicle_name,
            )
        )

    if scenario.status in (ScenarioStatus.DRAFT, ScenarioStatus.FAILED):
        scenario.status = ScenarioStatus.READY
        await db.commit()

    return FeasibilityPreviewResponse(
        scenario_id=scenario.id,
        feasible_vehicles=feasible_schemas,
        rejected_vehicles=rejected_schemas,
        consolidation_options=consolidations,
    )


@router.post(
    "/run",
    response_model=OptimizationResponse,
    summary="Run optimization engine",
)
async def run_optimization(
    payload: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Run full optimization pipeline and generate routes."""
    scenario, db_vehicles = await _load_scenario_data(db, payload.scenario_id, principal)
    if not scenario.harvests:
        raise HTTPException(status_code=400, detail="Scenario has no harvests")
    # Reserve guest quota before heavy work (fails fast at limit)
    if principal.is_guest:
        if principal.session_id is None:
            raise HTTPException(status_code=401, detail="Guest session missing")
        demo = await db.get(DemoSession, principal.session_id)
        if demo is None:
            raise HTTPException(status_code=401, detail="Guest session not found")
        if demo.runs_used >= settings.guest_max_optimize_runs:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Guest demo limit reached ({settings.guest_max_optimize_runs} runs). "
                    "Sign up to continue."
                ),
            )

    now = datetime.now(timezone.utc)
    
    # Very basic preparation to feed the optimizer (same as preview)
    risk_inputs = [
        HarvestRiskInput(
            harvest_id=str(h.id),
            label=h.label,
            commodity=CommodityInfo(
                perishability_class=h.commodity.perishability_class,
                shelf_life_hours=h.commodity.shelf_life_hours,
                default_price_idr_per_kg=h.commodity.default_price_idr_per_kg,
            ),
            harvested_at=h.harvested_at,
            handling_factor=h.handling_factor,
        ) for h in scenario.harvests
    ]
    risk_results = {r.harvest_id: r for r in score_harvests(risk_inputs, reference_time=now)}

    demands = [
        HarvestDemand(
            harvest_id=str(h.id),
            label=h.label,
            volume_kg=h.volume_kg,
            pickup_lat=h.location_lat,
            pickup_lng=h.location_lng,
            destination_lat=h.destination_lat,
            destination_lng=h.destination_lng,
            recommended_max_transit_hours=risk_results[str(h.id)].recommended_max_transit_hours,
        ) for h in scenario.harvests
    ]
    
    avg_price = sum(h.commodity.default_price_idr_per_kg for h in scenario.harvests) / len(scenario.harvests)
    total_volume = sum(h.volume_kg for h in scenario.harvests)

    candidates = [
        VehicleCandidate(
            vehicle_id=str(v.id), name=v.name, capacity_kg=v.capacity_kg,
            current_lat=v.current_location_lat, current_lng=v.current_location_lng,
            available_from=v.available_from, available_until=v.available_until,
            cost_per_km_idr=v.cost_per_km_idr,
        ) for v in db_vehicles
    ]

    feasible, _ = filter_feasible_vehicles(candidates, demands, planned_departure=now)
    if not feasible:
        raise HTTPException(status_code=400, detail="No feasible vehicles found for this scenario.")

    feasible_ids = {f.vehicle_id for f in feasible}
    if payload.vehicle_id is None:
        raise HTTPException(
            status_code=400,
            detail="vehicle_id is required. Run POST /optimization/preview and pick a feasible vehicle.",
        )
    chosen_id = str(payload.vehicle_id)
    if chosen_id not in feasible_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Vehicle {chosen_id} is not feasible for this scenario's harvests.",
        )
    best_vehicle = next(c for c in candidates if c.vehicle_id == chosen_id)

    scenario.status = ScenarioStatus.OPTIMIZING
    await db.flush()

    # Run optimizer
    adapter = RoutingAdapter()
    optimizer = RouteOptimizer(adapter)
    run_id = str(uuid.uuid4())

    baseline_res, optimized_res = await optimizer.optimize(
        run_id=run_id,
        vehicle=best_vehicle,
        harvests=demands,
        mode=payload.mode.value,
    )

    # Calculate economic impact
    impact = calculate_impact(
        baseline_risk_score=baseline_res.risk_score,
        optimized_risk_score=optimized_res.risk_score,
        total_volume_kg=total_volume,
        avg_commodity_price_idr=avg_price,
        baseline_cost_idr=baseline_res.cost_idr,
        optimized_cost_idr=optimized_res.cost_idr,
    )

    # Persist the run
    run_record = OptimizationRun(
        id=uuid.UUID(run_id),
        scenario_id=scenario.id,
        formula_version=settings.risk_formula_version,
        alpha=settings.alpha_travel_cost,
        beta=settings.beta_detour_cost,
        gamma=settings.gamma_spoilage_risk,
        food_loss_avoided_kg=impact.food_loss_avoided_kg,
        economic_loss_avoided_idr=impact.economic_loss_avoided_idr,
        additional_logistics_cost_idr=impact.additional_logistics_cost_idr,
        net_value_idr=impact.net_value_idr,
    )
    
    base_db = RouteResultData(
        run_id=run_record.id,
        result_type="baseline",
        vehicle_id=baseline_res.vehicle_id,
        pickup_sequence=baseline_res.pickup_sequence,
        distance_km=baseline_res.distance_km,
        duration_hours=baseline_res.duration_hours,
        risk_score=baseline_res.risk_score,
        cost_idr=baseline_res.cost_idr,
        geometry=baseline_res.geometry,
    )
    
    opt_db = RouteResultData(
        run_id=run_record.id,
        result_type="spoilage_aware",
        vehicle_id=optimized_res.vehicle_id,
        pickup_sequence=optimized_res.pickup_sequence,
        distance_km=optimized_res.distance_km,
        duration_hours=optimized_res.duration_hours,
        risk_score=optimized_res.risk_score,
        cost_idr=optimized_res.cost_idr,
        geometry=optimized_res.geometry,
    )

    db.add(run_record)
    db.add(base_db)
    db.add(opt_db)
    
    scenario.status = ScenarioStatus.COMPLETED
    scenario.optimization_mode = payload.mode

    await _consume_guest_run(db, principal)

    await db.commit()

    return OptimizationResponse(
        scenario_id=scenario.id,
        mode=payload.mode,
        baseline_route=RouteResultSchema(**baseline_res.__dict__),
        spoilage_aware_route=RouteResultSchema(**optimized_res.__dict__),
        estimated_food_loss_avoided_kg=impact.food_loss_avoided_kg,
        economic_loss_avoided_idr=impact.economic_loss_avoided_idr,
        additional_logistics_cost_idr=impact.additional_logistics_cost_idr,
        net_value_idr=impact.net_value_idr,
    )
