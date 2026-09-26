"""Scenario model — represents a planning scenario that groups harvests for optimization.

A scenario is the top-level container: the operator creates a scenario,
adds harvest inputs, selects a mode, then runs the optimization.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ScenarioStatus(str, enum.Enum):
    """Status of a planning scenario."""

    DRAFT = "draft"
    READY = "ready"
    OPTIMIZING = "optimizing"
    COMPLETED = "completed"
    FAILED = "failed"


class OptimizationMode(str, enum.Enum):
    """Optimization mode that determines α/β/γ weight presets."""

    COST_PRIORITY = "cost_priority"
    BALANCED = "balanced"
    SPOILAGE_PRIORITY = "spoilage_priority"


class Scenario(Base):
    """A planning scenario grouping one or more harvests for optimization.

    The operator creates a scenario, adds harvests, selects a mode,
    and runs the optimization to produce route recommendations.
    """

    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ScenarioStatus] = mapped_column(
        Enum(ScenarioStatus), default=ScenarioStatus.DRAFT, nullable=False
    )
    optimization_mode: Mapped[OptimizationMode] = mapped_column(
        Enum(OptimizationMode), default=OptimizationMode.BALANCED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    harvests: Mapped[list["Harvest"]] = relationship(  # noqa: F821
        back_populates="scenario", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Scenario(name={self.name!r}, status={self.status})>"
