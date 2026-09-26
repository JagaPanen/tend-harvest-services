"""Harvest model — represents an individual harvest input within a scenario.

Each harvest has a location (GPS), commodity type, volume, harvest time,
delivery destination, and optional handling factor.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Harvest(Base):
    """A single harvest data point within a planning scenario.

    Links to a commodity for perishability classification and to a scenario
    as the parent planning container.
    """

    __tablename__ = "harvests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    commodity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commodities.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Short label e.g. 'A', 'B', 'Harvest-1'"
    )
    location_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="Harvest latitude")
    location_lng: Mapped[float] = mapped_column(Float, nullable=False, comment="Harvest longitude")
    volume_kg: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Harvest volume in kilograms"
    )
    harvested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Actual harvest timestamp"
    )
    destination_lat: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Delivery destination latitude"
    )
    destination_lng: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Delivery destination longitude"
    )
    destination_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Destination",
        comment="Human-readable destination name"
    )
    handling_factor: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="Handling multiplier: 1.0 = standard, >1.0 = suboptimal conditions"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scenario: Mapped["Scenario"] = relationship(back_populates="harvests")  # noqa: F821
    commodity: Mapped["Commodity"] = relationship(back_populates="harvests")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Harvest(label={self.label!r}, volume={self.volume_kg}kg)>"
