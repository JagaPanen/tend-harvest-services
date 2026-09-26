"""Optimization Run models for persistence."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OptimizationRun(Base):
    """Stores the configuration and output of a single optimization run."""

    __tablename__ = "optimization_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    formula_version: Mapped[str] = mapped_column(String(50), nullable=False)
    alpha: Mapped[float] = mapped_column(Float, nullable=False)
    beta: Mapped[float] = mapped_column(Float, nullable=False)
    gamma: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # Impact metrics
    food_loss_avoided_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    economic_loss_avoided_idr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    additional_logistics_cost_idr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_value_idr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationships
    route_results: Mapped[list["RouteResultData"]] = relationship(  # noqa: F821
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    explanations: Mapped[list["DecisionExplanation"]] = relationship(  # noqa: F821
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class RouteResultData(Base):
    """Stores a route result (baseline or optimized) generated during a run."""

    __tablename__ = "route_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False
    )
    result_type: Mapped[str] = mapped_column(String(50), nullable=False)  # baseline or spoilage_aware
    vehicle_id: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Simple list of labels or IDs stored as JSON for SQLite compatibility in tests
    # If using pure Postgres, ARRAY(String) could be used. JSON is safer across DBs.
    pickup_sequence: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    cost_idr: Mapped[float] = mapped_column(Float, nullable=False)
    geometry: Mapped[str] = mapped_column(String, nullable=False)

    run: Mapped["OptimizationRun"] = relationship(back_populates="route_results")  # noqa: F821


class DecisionExplanation(Base):
    """Stores explanations for consolidation and routing decisions."""

    __tablename__ = "decision_explanations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False
    )
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)

    run: Mapped["OptimizationRun"] = relationship(back_populates="explanations")  # noqa: F821
