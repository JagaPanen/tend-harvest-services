"""Billing endpoints — usage, checkout stub, Xendit webhook."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal
from app.core.config import settings
from app.core.database import get_db
from app.models.organization import Organization
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    DevSetUsageRequest,
    UsageResponse,
    WebhookPayload,
)
from app.services.billing.checkout import apply_webhook_payment, create_checkout
from app.services.billing.usage import build_usage_snapshot, get_or_create_counter

router = APIRouter(prefix="/billing", tags=["Billing"])


def _require_org_user(principal: Principal) -> None:
    if principal.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Billing is only available for organization accounts",
        )


def _snapshot_to_response(snap) -> UsageResponse:
    return UsageResponse(
        plan=snap.plan,
        period_key=snap.period_key,
        optimize_runs_used=snap.optimize_runs_used,
        optimize_runs_limit=snap.optimize_runs_limit,
        usage_ratio=snap.usage_ratio,
        soft_warning=snap.soft_warning,
        hard_blocked=snap.hard_blocked,
        pilot_ends_at=snap.pilot_ends_at,
        pilot_expired=snap.pilot_expired,
        upgrade_required=snap.upgrade_required,
        message=snap.message,
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> UsageResponse:
    _require_org_user(principal)
    org = await db.get(Organization, principal.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    snap = await build_usage_snapshot(db, org)
    return _snapshot_to_response(snap)


@router.post("/checkout", response_model=CheckoutResponse)
async def start_checkout(
    payload: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> CheckoutResponse:
    _require_org_user(principal)
    org = await db.get(Organization, principal.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    stub = settings.billing_stub or not settings.xendit_secret_key.strip()
    sub = await create_checkout(
        db, org, payload.plan, activate_stub=payload.activate_stub and stub
    )
    await db.commit()

    if stub:
        msg = (
            "Stub checkout activated — plan is live."
            if payload.activate_stub
            else (
                "Stub checkout created. Complete payment by POSTing "
                f"/billing/webhook with external_id={sub.external_id} and status=PAID, "
                "or call checkout again with activate_stub=true."
            )
        )
    else:
        msg = (
            "Pending Xendit invoice row created. Configure Invoice API or "
            "complete via webhook when paid."
        )

    return CheckoutResponse(
        mode="stub" if stub else "xendit",
        plan=sub.plan,
        status=sub.status,
        external_id=sub.external_id,
        checkout_url=sub.checkout_url,
        subscription_id=sub.id,
        message=msg,
    )


@router.post("/webhook")
async def billing_webhook(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
    x_callback_token: str | None = Header(default=None, alias="x-callback-token"),
) -> dict:
    """Xendit-compatible webhook (also used by the documented stub)."""
    expected = settings.xendit_webhook_token.strip()
    if expected and x_callback_token != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    external_id = payload.external_id
    status_value = payload.status
    if payload.data and isinstance(payload.data, dict):
        external_id = external_id or payload.data.get("external_id")
        status_value = payload.data.get("status") or status_value

    if not external_id:
        raise HTTPException(status_code=400, detail="external_id required")

    sub = await apply_webhook_payment(
        db, external_id=str(external_id), status_value=str(status_value)
    )
    await db.commit()
    return {
        "ok": True,
        "subscription_id": str(sub.id),
        "plan": sub.plan,
        "status": sub.status,
    }


@router.post("/dev/set-usage", response_model=UsageResponse)
async def dev_set_usage(
    payload: DevSetUsageRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> UsageResponse:
    """DEBUG only — set run meter for Pilot limit demos."""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")
    _require_org_user(principal)
    org = await db.get(Organization, principal.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    counter = await get_or_create_counter(db, org)
    counter.optimize_runs_used = payload.optimize_runs_used
    await db.commit()
    snap = await build_usage_snapshot(db, org)
    return _snapshot_to_response(snap)
