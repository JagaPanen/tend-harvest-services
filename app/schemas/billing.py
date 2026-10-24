"""Billing API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UsageResponse(BaseModel):
    plan: str
    period_key: str
    optimize_runs_used: int
    optimize_runs_limit: int | None
    usage_ratio: float
    soft_warning: bool
    hard_blocked: bool
    pilot_ends_at: datetime | None = None
    pilot_expired: bool = False
    upgrade_required: bool = False
    message: str | None = None


class CheckoutRequest(BaseModel):
    plan: str = Field(description="starter | fleet")
    activate_stub: bool = Field(
        default=False,
        description="When billing stub mode is on, immediately activate the plan",
    )


class CheckoutResponse(BaseModel):
    mode: str  # stub | xendit
    plan: str
    status: str
    external_id: str
    checkout_url: str | None = None
    subscription_id: uuid.UUID
    message: str


class WebhookPayload(BaseModel):
    """Accepts a slim Xendit-like payload (or stub)."""

    external_id: str | None = None
    id: str | None = None  # some Xendit events use id
    status: str = "PAID"
    # Nested invoice style
    data: dict | None = None


class DevSetUsageRequest(BaseModel):
    optimize_runs_used: int = Field(ge=0)
