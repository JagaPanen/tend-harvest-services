"""Xendit checkout stub + webhook activation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Subscription, UsageCounter
from app.models.organization import Organization
from app.services.billing.plans import PAID_CHECKOUT_PLANS, normalize_plan
from app.services.billing.usage import period_key_for_plan


def _stub_mode() -> bool:
    return settings.billing_stub or not settings.xendit_secret_key.strip()


async def create_checkout(
    db: AsyncSession,
    org: Organization,
    plan: str,
    *,
    activate_stub: bool = False,
) -> Subscription:
    plan = normalize_plan(plan)
    if plan not in PAID_CHECKOUT_PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checkout only supports plan=pro",
        )

    external_id = f"jp-{org.id.hex[:8]}-{plan}-{uuid.uuid4().hex[:10]}"
    base = settings.billing_public_app_url.rstrip("/")
    qs = urlencode({"checkout": "pending", "plan": plan, "external_id": external_id})
    checkout_url = f"{base}/app/settings/billing?{qs}"

    sub = Subscription(
        organization_id=org.id,
        plan=plan,
        status="pending",
        external_id=external_id,
        xendit_invoice_id=None,
        checkout_url=checkout_url,
    )
    db.add(sub)
    await db.flush()

    if _stub_mode() and activate_stub:
        await activate_subscription(db, org, sub)
        return sub

    if not _stub_mode():
        # Live secret present: keep pending row; FE/docs use webhook to activate.
        # Real Xendit Invoice create can replace checkout_url later.
        sub.xendit_invoice_id = f"xendit-pending-{external_id}"
        await db.flush()

    return sub


async def activate_subscription(
    db: AsyncSession, org: Organization, sub: Subscription
) -> Subscription:
    now = datetime.now(timezone.utc)
    sub.status = "active"
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)

    org.plan = sub.plan
    org.pilot_ends_at = None

    key = period_key_for_plan(sub.plan, now)
    existing = (
        await db.execute(
            select(UsageCounter).where(
                UsageCounter.organization_id == org.id,
                UsageCounter.period_key == key,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            UsageCounter(
                organization_id=org.id,
                period_key=key,
                optimize_runs_used=0,
            )
        )
    else:
        existing.optimize_runs_used = 0

    await db.flush()
    return sub


async def apply_webhook_payment(
    db: AsyncSession,
    *,
    external_id: str,
    status_value: str,
) -> Subscription:
    result = await db.execute(
        select(Subscription).where(Subscription.external_id == external_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=404, detail="Subscription not found for external_id"
        )

    org = await db.get(Organization, sub.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    normalized = status_value.upper()
    if normalized in ("PAID", "SETTLED", "COMPLETED", "ACTIVE"):
        await activate_subscription(db, org, sub)
    elif normalized in ("EXPIRED", "FAILED", "CANCELLED"):
        sub.status = "failed" if normalized == "FAILED" else "expired"
        await db.flush()
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unhandled webhook status: {status_value}",
        )
    return sub
