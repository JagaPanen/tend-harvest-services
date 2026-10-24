"""Optimization API endpoints.

POST /api/v1/optimization/preview — Feasibility check
POST /api/v1/optimization/run — Generate routes
GET /api/v1/optimization/runs — List runs (org only)
GET /api/v1/optimization/runs/{id} — Retrieve run (org only)
GET /api/v1/optimization/runs/{id}/report — CSV decision report (org only; 403 guest)
"""

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import Principal, get_current_principal
from app.core.config import settings
from app.core.database import get_db
from app.core.tenancy import get_org_scenario
from app.models.harvest import Harvest
from app.models.optimization_run import OptimizationRun, RouteResultData
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
    OptimizationRunDetail,
    OptimizationRunSummary,
    RouteResultSchema,
)

from app.services.billing.usage import assert_org_can_optimize, consume_org_run
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
    scenario, db_vehicles = await _load_scenario_data(
        db, payload.scenario_id, principal
    )
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
        )
        for h in scenario.harvests
    ]
    risk_results = {
        r.harvest_id: r for r in score_harvests(risk_inputs, reference_time=now)
    }

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
            recommended_max_transit_hours=risk_results[
                str(h.id)
            ].recommended_max_transit_hours,
            urgency_score=risk_results[str(h.id)].urgency_score,
        )
        for h in scenario.harvests
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
        )
        for v in db_vehicles
    ]

    # 4. Check feasibility
    feasible, rejected = filter_feasible_vehicles(
        candidates, demands, planned_departure=now
    )

    feasible_schemas = [
        FeasibleVehicle(
            vehicle_id=uuid.UUID(f.vehicle_id),
            vehicle_name=f.vehicle_name,
            is_feasible=True,
            reasons=f.reasons,
            total_volume_kg=f.total_demand_kg,
            remaining_capacity_kg=f.remaining_capacity_kg,
        )
        for f in feasible
    ]
    rejected_schemas = [
        FeasibleVehicle(
            vehicle_id=uuid.UUID(r.vehicle_id),
            vehicle_name=r.vehicle_name,
            is_feasible=False,
            reasons=r.reasons,
            total_volume_kg=r.total_demand_kg,
            remaining_capacity_kg=r.remaining_capacity_kg,
        )
        for r in rejected
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
    # Reserve quota before any DB work (fails fast at plan / guest limit)
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
    else:
        await assert_org_can_optimize(db, principal.org_id)

    scenario, db_vehicles = await _load_scenario_data(
        db, payload.scenario_id, principal
    )
    if not scenario.harvests:
        raise HTTPException(status_code=400, detail="Scenario has no harvests")

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
        )
        for h in scenario.harvests
    ]
    risk_results = {
        r.harvest_id: r for r in score_harvests(risk_inputs, reference_time=now)
    }

    demands = [
        HarvestDemand(
            harvest_id=str(h.id),
            label=h.label,
            volume_kg=h.volume_kg,
            pickup_lat=h.location_lat,
            pickup_lng=h.location_lng,
            destination_lat=h.destination_lat,
            destination_lng=h.destination_lng,
            recommended_max_transit_hours=risk_results[
                str(h.id)
            ].recommended_max_transit_hours,
            urgency_score=risk_results[str(h.id)].urgency_score,
        )
        for h in scenario.harvests
    ]

    avg_price = sum(
        h.commodity.default_price_idr_per_kg for h in scenario.harvests
    ) / len(scenario.harvests)
    total_volume = sum(h.volume_kg for h in scenario.harvests)

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
        )
        for v in db_vehicles
    ]

    feasible, _ = filter_feasible_vehicles(candidates, demands, planned_departure=now)
    if not feasible:
        raise HTTPException(
            status_code=400, detail="No feasible vehicles found for this scenario."
        )

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
    if not principal.is_guest:
        await consume_org_run(db, principal.org_id)

    await db.commit()

    return OptimizationResponse(
        scenario_id=scenario.id,
        run_id=run_record.id,
        mode=payload.mode,
        baseline_route=RouteResultSchema(**baseline_res.__dict__),
        spoilage_aware_route=RouteResultSchema(**optimized_res.__dict__),
        estimated_food_loss_avoided_kg=impact.food_loss_avoided_kg,
        economic_loss_avoided_idr=impact.economic_loss_avoided_idr,
        additional_logistics_cost_idr=impact.additional_logistics_cost_idr,
        net_value_idr=impact.net_value_idr,
    )


def _require_org(principal: Principal) -> None:
    if principal.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Optimization history and export require an organization account. Please sign up.",
        )


def _route_row_to_schema(row: RouteResultData) -> RouteResultSchema:
    return RouteResultSchema(
        run_id=str(row.run_id),
        result_type=row.result_type,  # type: ignore[arg-type]
        mode=row.result_type,
        vehicle_id=row.vehicle_id,
        pickup_sequence=list(row.pickup_sequence or []),
        distance_km=row.distance_km,
        duration_hours=row.duration_hours,
        risk_score=row.risk_score,
        cost_idr=row.cost_idr,
        geometry=row.geometry or "",
    )


async def _get_org_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    principal: Principal,
) -> OptimizationRun:
    result = await db.execute(
        select(OptimizationRun)
        .options(selectinload(OptimizationRun.route_results))
        .join(Scenario, Scenario.id == OptimizationRun.scenario_id)
        .where(
            OptimizationRun.id == run_id,
            Scenario.organization_id == principal.org_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Optimization run not found")
    return run


@router.get(
    "/runs",
    response_model=list[OptimizationRunSummary],
    summary="List optimization runs for the current org",
)
async def list_optimization_runs(
    scenario_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _require_org(principal)
    stmt = (
        select(OptimizationRun, Scenario.name)
        .join(Scenario, Scenario.id == OptimizationRun.scenario_id)
        .where(Scenario.organization_id == principal.org_id)
        .order_by(OptimizationRun.created_at.desc())
        .limit(100)
    )
    if scenario_id is not None:
        await get_org_scenario(db, scenario_id, principal)
        stmt = stmt.where(OptimizationRun.scenario_id == scenario_id)

    rows = (await db.execute(stmt)).all()
    out: list[OptimizationRunSummary] = []
    for run, scenario_name in rows:
        out.append(
            OptimizationRunSummary(
                id=run.id,
                scenario_id=run.scenario_id,
                scenario_name=scenario_name,
                created_at=run.created_at.isoformat() if run.created_at else "",
                formula_version=run.formula_version,
                alpha=run.alpha,
                beta=run.beta,
                gamma=run.gamma,
                food_loss_avoided_kg=run.food_loss_avoided_kg,
                economic_loss_avoided_idr=run.economic_loss_avoided_idr,
                additional_logistics_cost_idr=run.additional_logistics_cost_idr,
                net_value_idr=run.net_value_idr,
            )
        )
    return out


@router.get(
    "/runs/{run_id}",
    response_model=OptimizationRunDetail,
    summary="Get optimization run detail for ComparisonView replay",
)
async def get_optimization_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _require_org(principal)
    run = await _get_org_run(db, run_id, principal)
    scenario = await db.get(Scenario, run.scenario_id)
    baseline = next((r for r in run.route_results if r.result_type == "baseline"), None)
    spoilage = next(
        (r for r in run.route_results if r.result_type == "spoilage_aware"), None
    )
    return OptimizationRunDetail(
        id=run.id,
        scenario_id=run.scenario_id,
        scenario_name=scenario.name if scenario else None,
        created_at=run.created_at.isoformat() if run.created_at else "",
        formula_version=run.formula_version,
        alpha=run.alpha,
        beta=run.beta,
        gamma=run.gamma,
        food_loss_avoided_kg=run.food_loss_avoided_kg,
        economic_loss_avoided_idr=run.economic_loss_avoided_idr,
        additional_logistics_cost_idr=run.additional_logistics_cost_idr,
        net_value_idr=run.net_value_idr,
        baseline_route=_route_row_to_schema(baseline) if baseline else None,
        spoilage_aware_route=_route_row_to_schema(spoilage) if spoilage else None,
    )


@router.get(
    "/runs/{run_id}/report",
    summary="Download CSV decision report (org only)",
)
async def download_optimization_report(
    run_id: uuid.UUID,
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    _require_org(principal)
    run = await _get_org_run(db, run_id, principal)
    scenario = await db.get(Scenario, run.scenario_id)
    baseline = next((r for r in run.route_results if r.result_type == "baseline"), None)
    spoilage = next(
        (r for r in run.route_results if r.result_type == "spoilage_aware"), None
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["JagaPanen Decision Report"])
    writer.writerow(["run_id", str(run.id)])
    writer.writerow(["scenario_id", str(run.scenario_id)])
    writer.writerow(["scenario_name", scenario.name if scenario else ""])
    writer.writerow(
        ["created_at", run.created_at.isoformat() if run.created_at else ""]
    )
    writer.writerow(["formula_version", run.formula_version])
    writer.writerow(["alpha", run.alpha])
    writer.writerow(["beta", run.beta])
    writer.writerow(["gamma", run.gamma])
    writer.writerow([])
    writer.writerow(
        [
            "metric",
            "baseline",
            "spoilage_aware",
            "delta",
        ]
    )

    def row(metric: str, b: float | str, s: float | str) -> None:
        try:
            bf = float(b)
            sf = float(s)
            delta: float | str = round(sf - bf, 4)
        except (TypeError, ValueError):
            delta = ""
        writer.writerow([metric, b, s, delta])

    row(
        "distance_km",
        baseline.distance_km if baseline else "",
        spoilage.distance_km if spoilage else "",
    )
    row(
        "duration_hours",
        baseline.duration_hours if baseline else "",
        spoilage.duration_hours if spoilage else "",
    )
    row(
        "risk_score",
        baseline.risk_score if baseline else "",
        spoilage.risk_score if spoilage else "",
    )
    row(
        "cost_idr",
        baseline.cost_idr if baseline else "",
        spoilage.cost_idr if spoilage else "",
    )
    writer.writerow([])
    writer.writerow(["food_loss_avoided_kg", run.food_loss_avoided_kg])
    writer.writerow(["economic_loss_avoided_idr", run.economic_loss_avoided_idr])
    writer.writerow(
        ["additional_logistics_cost_idr", run.additional_logistics_cost_idr]
    )
    writer.writerow(["net_value_idr", run.net_value_idr])
    writer.writerow([])
    writer.writerow(
        [
            "baseline_pickup_sequence",
            " → ".join(baseline.pickup_sequence if baseline else []),
        ]
    )
    writer.writerow(
        [
            "spoilage_pickup_sequence",
            " → ".join(spoilage.pickup_sequence if spoilage else []),
        ]
    )
    writer.writerow([])
    writer.writerow(
        [
            "assumptions",
            "Rule-based risk scorer + α/β/γ OR-Tools TSP; Mapbox/OSRM geometry when available",
        ]
    )

    payload = buf.getvalue().encode("utf-8")
    # PDF format: same CSV body with .pdf filename for board print-to-PDF workflows (no extra deps)
    filename = f"jagapanen-run-{run.id}.{'pdf' if format == 'pdf' else 'csv'}"
    media = "application/pdf" if format == "pdf" else "text/csv"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
