"""Plan catalog — Basic (default) and Pro (paid). Guest remains demo-only."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

# Org plans exposed in product / checkout
ORG_PLANS = frozenset({"basic", "pro"})
PAID_CHECKOUT_PLANS = frozenset({"pro"})

# Older plan keys still present in DB / bookmarks → canonical
_LEGACY_PLAN_ALIASES: dict[str, str] = {
    "pilot": "basic",
    "starter": "basic",
    "fleet": "pro",
    "enterprise": "pro",
}


def normalize_plan(plan: str) -> str:
    """Map legacy plan names to basic | pro (guest unchanged)."""
    key = (plan or "basic").lower().strip()
    if key == "guest":
        return "guest"
    return _LEGACY_PLAN_ALIASES.get(key, key if key in ORG_PLANS else "basic")


@dataclass(frozen=True)
class PlanInfo:
    key: str
    label: str
    max_runs: int | None  # None = unlimited
    monthly: bool
    price_idr_monthly: int | None


PLAN_CATALOG: dict[str, PlanInfo] = {
    "guest": PlanInfo(
        "guest", "Guest Demo", settings.guest_max_optimize_runs, False, None
    ),
    "basic": PlanInfo(
        "basic", "Basic", settings.basic_max_optimize_runs, True, 0
    ),
    "pro": PlanInfo(
        "pro", "Pro", settings.pro_max_optimize_runs, True, 49_000
    ),
}


def plan_run_limit(plan: str) -> int | None:
    key = normalize_plan(plan)
    if key == "guest":
        return settings.guest_max_optimize_runs
    if key == "basic":
        return settings.basic_max_optimize_runs
    if key == "pro":
        return settings.pro_max_optimize_runs
    return settings.basic_max_optimize_runs
