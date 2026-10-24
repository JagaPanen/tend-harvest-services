"""Plan catalog and run limits (JagaPanen V2 P4)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

PAID_CHECKOUT_PLANS = frozenset({"starter", "fleet"})


@dataclass(frozen=True)
class PlanInfo:
    key: str
    label: str
    max_runs: int | None  # None = unlimited (enterprise)
    monthly: bool
    price_idr_monthly: int | None


PLAN_CATALOG: dict[str, PlanInfo] = {
    "guest": PlanInfo(
        "guest", "Guest Demo", settings.guest_max_optimize_runs, False, None
    ),
    "pilot": PlanInfo(
        "pilot", "Free Pilot", settings.pilot_max_optimize_runs, False, 0
    ),
    "starter": PlanInfo(
        "starter", "Starter", settings.starter_max_optimize_runs, True, 499_000
    ),
    "fleet": PlanInfo(
        "fleet", "Fleet", settings.fleet_max_optimize_runs, True, 1_499_000
    ),
    "enterprise": PlanInfo("enterprise", "Enterprise", None, False, None),
}


def plan_run_limit(plan: str) -> int | None:
    info = PLAN_CATALOG.get(plan.lower())
    if info is None:
        return settings.pilot_max_optimize_runs
    # Re-read env-backed limits for metered plans
    key = plan.lower()
    if key == "pilot":
        return settings.pilot_max_optimize_runs
    if key == "starter":
        return settings.starter_max_optimize_runs
    if key == "fleet":
        return settings.fleet_max_optimize_runs
    if key == "guest":
        return settings.guest_max_optimize_runs
    return info.max_runs
