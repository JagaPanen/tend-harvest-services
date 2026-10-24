"""Subscriptions and optimize-run usage counters (JagaPanen V2 P4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UsageCounter(Base):
    """Per-org optimize-run meter for the current plan period."""

    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_key", name="uq_usage_org_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    # "YYYY-MM" for Basic / Pro monthly meters
    period_key: Mapped[str] = mapped_column(String(32), nullable=False)
    optimize_runs_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Subscription(Base):
    """Checkout / Xendit (or stub) subscription row."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String(50), nullable=False)  # basic | pro
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )  # pending | active | expired | failed
    external_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    xendit_invoice_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
