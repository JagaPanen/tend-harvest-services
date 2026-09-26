"""Risk Scoring API endpoints.

POST /api/v1/risk/score — Calculate spoilage risk for one or more harvests.
Accepts persisted harvest IDs and/or inline harvest data.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.commodity import Commodity
from app.models.harvest import Harvest
from app.schemas.risk import (
    RiskScoreRequest,
    RiskScoreResponse,
    RiskScoreItemResponse,
)
from app.services.risk.scorer import (
    CommodityInfo,
    HarvestRiskInput,
    score_harvests,
)

router = APIRouter(prefix="/risk", tags=["Risk Scoring"])


async def _load_commodity(db: AsyncSession, commodity_id: uuid.UUID) -> Commodity:
    """Load a commodity by ID or raise 404."""
    result = await db.execute(select(Commodity).where(Commodity.id == commodity_id))
    commodity = result.scalar_one_or_none()
    if commodity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Commodity {commodity_id} not found",
        )
    return commodity


@router.post(
    "/score",
    response_model=RiskScoreResponse,
    summary="Calculate spoilage risk",
    description=(
        "Score one or more harvests for spoilage risk using the rule-based formula. "
        "Provide `harvest_ids` to score persisted harvests, or `harvests` for inline data. "
        "Results are sorted by urgency (highest risk first)."
    ),
)
async def score_risk(
    payload: RiskScoreRequest,
    db: AsyncSession = Depends(get_db),
) -> RiskScoreResponse:
    """Calculate risk scores for the provided harvests."""

    # Validate that at least one input is provided
    has_ids = payload.harvest_ids and len(payload.harvest_ids) > 0
    has_inline = payload.harvests and len(payload.harvests) > 0

    if not has_ids and not has_inline:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one of 'harvest_ids' or 'harvests'.",
        )

    risk_inputs: list[HarvestRiskInput] = []

    # ── Resolve persisted harvests ───────────────────────────────────────
    if has_ids:
        result = await db.execute(
            select(Harvest).where(Harvest.id.in_(payload.harvest_ids))
        )
        db_harvests = result.scalars().all()

        found_ids = {h.id for h in db_harvests}
        missing = [str(hid) for hid in payload.harvest_ids if hid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Harvests not found: {', '.join(missing)}",
            )

        # Preload commodities for all harvests
        commodity_ids = {h.commodity_id for h in db_harvests}
        comm_result = await db.execute(
            select(Commodity).where(Commodity.id.in_(commodity_ids))
        )
        commodities_map = {c.id: c for c in comm_result.scalars().all()}

        for h in db_harvests:
            c = commodities_map[h.commodity_id]
            risk_inputs.append(
                HarvestRiskInput(
                    harvest_id=str(h.id),
                    label=h.label,
                    commodity=CommodityInfo(
                        perishability_class=c.perishability_class,
                        shelf_life_hours=c.shelf_life_hours,
                        default_price_idr_per_kg=c.default_price_idr_per_kg,
                    ),
                    harvested_at=h.harvested_at,
                    handling_factor=h.handling_factor,
                    estimated_transit_hours=payload.estimated_transit_hours,
                )
            )

    # ── Resolve inline harvests ──────────────────────────────────────────
    if has_inline:
        # Batch-load referenced commodities
        inline_commodity_ids = {h.commodity_id for h in payload.harvests}
        comm_result = await db.execute(
            select(Commodity).where(Commodity.id.in_(inline_commodity_ids))
        )
        commodities_map_inline = {c.id: c for c in comm_result.scalars().all()}

        missing_comms = inline_commodity_ids - set(commodities_map_inline.keys())
        if missing_comms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Commodities not found: {', '.join(str(c) for c in missing_comms)}",
            )

        for h in payload.harvests:
            c = commodities_map_inline[h.commodity_id]
            risk_inputs.append(
                HarvestRiskInput(
                    harvest_id=f"inline-{h.label}",
                    label=h.label,
                    commodity=CommodityInfo(
                        perishability_class=c.perishability_class,
                        shelf_life_hours=c.shelf_life_hours,
                        default_price_idr_per_kg=c.default_price_idr_per_kg,
                    ),
                    harvested_at=h.harvested_at,
                    handling_factor=h.handling_factor,
                    estimated_transit_hours=h.estimated_transit_hours,
                )
            )

    # ── Score all inputs ─────────────────────────────────────────────────
    results = score_harvests(risk_inputs, reference_time=payload.reference_time)

    return RiskScoreResponse(
        count=len(results),
        formula_version=settings.risk_formula_version,
        results=[
            RiskScoreItemResponse(
                harvest_id=r.harvest_id,
                label=r.label,
                perishability_class=r.perishability_class,
                urgency_score=r.urgency_score,
                recommended_max_transit_hours=r.recommended_max_transit_hours,
                priority_level=r.priority_level,
                time_since_harvest_hours=r.time_since_harvest_hours,
                estimated_transit_hours=r.estimated_transit_hours,
                shelf_life_hours=r.shelf_life_hours,
                handling_factor=r.handling_factor,
                formula_version=r.formula_version,
                explanation=r.explanation,
            )
            for r in results
        ],
    )
