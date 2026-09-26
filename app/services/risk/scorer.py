"""Spoilage Risk Scoring Engine — core business logic.

Implements the rule-based risk formula from the PRD:
    Risk Score = min(100, 100 × [(Time Since Harvest + Estimated Transit Time)
                / Shelf Life Reference] × Handling Factor)

Output per harvest:
    - perishability_class  (A–E from the commodity record)
    - urgency_score        (0–100, higher = more urgent)
    - recommended_max_transit_time  (hours remaining before score hits 80)
    - priority_level       (critical / high / medium / low)

Design principles:
    • Deterministic and reproducible — no ML, no randomness.
    • Formula version is tracked for auditability.
    • Pure functions: no database access; callers pass in the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings


# ── Priority thresholds ──────────────────────────────────────────────────────
# These map urgency_score ranges to human-readable priority levels.
PRIORITY_THRESHOLDS: list[tuple[float, str]] = [
    (80.0, "critical"),   # score >= 80
    (60.0, "high"),       # score >= 60
    (40.0, "medium"),     # score >= 40
    (0.0, "low"),         # score < 40
]


@dataclass(frozen=True)
class CommodityInfo:
    """Minimal commodity data needed for risk scoring."""

    perishability_class: str      # "A" – "E"
    shelf_life_hours: float       # e.g. 18.0 for tomatoes
    default_price_idr_per_kg: float


@dataclass(frozen=True)
class HarvestRiskInput:
    """Input data for scoring a single harvest."""

    harvest_id: str
    label: str
    commodity: CommodityInfo
    harvested_at: datetime
    handling_factor: float = 1.0
    estimated_transit_hours: float = 0.0  # caller may provide an estimate


@dataclass(frozen=True)
class RiskScoreResult:
    """Output of the risk scoring engine for a single harvest."""

    harvest_id: str
    label: str
    perishability_class: str
    urgency_score: float                    # 0–100
    recommended_max_transit_hours: float     # hours until score would hit 80
    priority_level: str                     # critical / high / medium / low
    time_since_harvest_hours: float
    estimated_transit_hours: float
    shelf_life_hours: float
    handling_factor: float
    formula_version: str
    explanation: str


def _priority_level(score: float) -> str:
    """Map an urgency score to a priority level string."""
    for threshold, level in PRIORITY_THRESHOLDS:
        if score >= threshold:
            return level
    return "low"


def _recommended_max_transit(
    time_since_harvest_hours: float,
    shelf_life_hours: float,
    handling_factor: float,
    target_score: float = 80.0,
) -> float:
    """Calculate the maximum transit hours before the risk score hits *target_score*.

    Derived from:
        target = 100 × [(tsh + transit) / shelf_life] × hf
        => transit = (target * shelf_life) / (100 * hf) - tsh

    Returns 0.0 if the harvest is already past the target.
    """
    if handling_factor <= 0 or shelf_life_hours <= 0:
        return 0.0
    max_transit = (target_score * shelf_life_hours) / (100.0 * handling_factor) - time_since_harvest_hours
    return max(0.0, round(max_transit, 2))


def calculate_risk_score(
    time_since_harvest_hours: float,
    estimated_transit_hours: float,
    shelf_life_hours: float,
    handling_factor: float,
) -> float:
    """Apply the PRD risk formula and return a score clamped to [0, 100].

    Formula:
        Risk Score = min(100, 100 × [(tsh + transit) / shelf_life] × hf)
    """
    if shelf_life_hours <= 0:
        return 100.0

    raw = 100.0 * ((time_since_harvest_hours + estimated_transit_hours) / shelf_life_hours) * handling_factor
    return round(min(100.0, max(0.0, raw)), 2)


def score_harvest(
    harvest: HarvestRiskInput,
    reference_time: datetime | None = None,
) -> RiskScoreResult:
    """Score a single harvest and return a full :class:`RiskScoreResult`.

    Parameters
    ----------
    harvest:
        The harvest data to score.
    reference_time:
        The "now" timestamp to use for calculating time since harvest.
        Defaults to ``datetime.now(timezone.utc)``.
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    # Ensure both datetimes are timezone-aware for subtraction
    harvested_at = harvest.harvested_at
    if harvested_at.tzinfo is None:
        harvested_at = harvested_at.replace(tzinfo=timezone.utc)

    time_since_harvest = (reference_time - harvested_at).total_seconds() / 3600.0
    time_since_harvest = max(0.0, time_since_harvest)  # don't allow negative

    score = calculate_risk_score(
        time_since_harvest_hours=time_since_harvest,
        estimated_transit_hours=harvest.estimated_transit_hours,
        shelf_life_hours=harvest.commodity.shelf_life_hours,
        handling_factor=harvest.handling_factor,
    )

    max_transit = _recommended_max_transit(
        time_since_harvest_hours=time_since_harvest,
        shelf_life_hours=harvest.commodity.shelf_life_hours,
        handling_factor=harvest.handling_factor,
    )

    priority = _priority_level(score)

    # Build human-readable explanation
    explanation = (
        f"{harvest.label}: {time_since_harvest:.1f}h since harvest + "
        f"{harvest.estimated_transit_hours:.1f}h transit = "
        f"{time_since_harvest + harvest.estimated_transit_hours:.1f}h total "
        f"against {harvest.commodity.shelf_life_hours}h shelf life "
        f"(class {harvest.commodity.perishability_class}, "
        f"handling ×{harvest.handling_factor}) → "
        f"score {score}, priority {priority}."
    )

    return RiskScoreResult(
        harvest_id=harvest.harvest_id,
        label=harvest.label,
        perishability_class=harvest.commodity.perishability_class,
        urgency_score=score,
        recommended_max_transit_hours=max_transit,
        priority_level=priority,
        time_since_harvest_hours=round(time_since_harvest, 2),
        estimated_transit_hours=harvest.estimated_transit_hours,
        shelf_life_hours=harvest.commodity.shelf_life_hours,
        handling_factor=harvest.handling_factor,
        formula_version=settings.risk_formula_version,
        explanation=explanation,
    )


def score_harvests(
    harvests: list[HarvestRiskInput],
    reference_time: datetime | None = None,
) -> list[RiskScoreResult]:
    """Score multiple harvests and return results sorted by urgency (highest first)."""
    results = [score_harvest(h, reference_time) for h in harvests]
    results.sort(key=lambda r: r.urgency_score, reverse=True)
    return results
