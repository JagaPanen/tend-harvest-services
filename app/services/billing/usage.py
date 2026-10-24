"""Org optimize-run metering and Pilot expiry checks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import UsageCounter
from app.models.organization import Organization
from app.services.billing.plans import plan_run_limit


def _now() -> datetime:
    return datetime.now(timezone.utc)


def period_key_for_plan(plan: str, at: datetime | None = None) -> str:
    at = at or _now()
    p = plan.lower()
    if p in ("starter", "fleet"):
        return at.strftime("%Y-%m")
    if p == "pilot":
        return "pilot"
    return p


@dataclass
class UsageSnapshot:
    plan: str
    period_key: str
    optimize_runs_used: int
    optimize_runs_limit: int | None
    usage_ratio: float
    soft_warning: bool
    hard_blocked: bool
    pilot_ends_at: datetime | None
    pilot_expired: bool
    upgrade_required: bool
    message: str | None


async def get_or_create_counter(db: AsyncSession, org: Organization) -> UsageCounter:
    key = period_key_for_plan(org.plan)
    result = await db.execute(
        select(UsageCounter).where(
            UsageCounter.organization_id == org.id,
            UsageCounter.period_key == key,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    row = UsageCounter(
        organization_id=org.id,
        period_key=key,
        optimize_runs_used=0,
    )
    db.add(row)
    await db.flush()
    return row


def _pilot_expired(org: Organization, now: datetime) -> bool:
    if org.plan.lower() != "pilot":
        return False
    if org.pilot_ends_at is None:
        return False
    ends = org.pilot_ends_at
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    return now >= ends


async def build_usage_snapshot(db: AsyncSession, org: Organization) -> UsageSnapshot:
    now = _now()
    expired = _pilot_expired(org, now)
    counter = await get_or_create_counter(db, org)
    limit = plan_run_limit(org.plan)
    used = counter.optimize_runs_used
    ratio = 0.0 if limit is None or limit <= 0 else min(1.0, used / limit)
    soft = bool(
        limit is not None and ratio >= settings.usage_soft_cap_ratio and used < limit
    )
    hard = bool(expired or (limit is not None and used >= limit))
    msg: str | None = None
    if expired:
        msg = "Pilot trial ended. Upgrade to Starter or Fleet to keep optimizing."
    elif hard and limit is not None:
        msg = (
            f"Plan run limit reached ({used}/{limit}). "
            "Upgrade to continue optimizing."
        )
    elif soft and limit is not None:
        msg = (
            f"You have used {used}/{limit} optimize runs "
            f"({int(ratio * 100)}%). Consider upgrading soon."
        )
    return UsageSnapshot(
        plan=org.plan,
        period_key=counter.period_key,
        optimize_runs_used=used,
        optimize_runs_limit=limit,
        usage_ratio=ratio,
        soft_warning=soft,
        hard_blocked=hard,
        pilot_ends_at=org.pilot_ends_at,
        pilot_expired=expired,
        upgrade_required=hard,
        message=msg,
    )


async def assert_org_can_optimize(db: AsyncSession, org_id: uuid.UUID) -> UsageSnapshot:
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if org.is_demo:
        # Demo tenant is guest-only; org users should not hit this path
        snap = await build_usage_snapshot(db, org)
        return snap
    snap = await build_usage_snapshot(db, org)
    if snap.hard_blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=snap.message or "Optimize run limit reached. Upgrade your plan.",
        )
    return snap


async def consume_org_run(db: AsyncSession, org_id: uuid.UUID) -> UsageSnapshot:
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if org.is_demo:
        return await build_usage_snapshot(db, org)
    counter = await get_or_create_counter(db, org)
    counter.optimize_runs_used += 1
    await db.flush()
    return await build_usage_snapshot(db, org)
