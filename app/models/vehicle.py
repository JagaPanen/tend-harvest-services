"""Vehicle model — represents transport vehicles available for harvest distribution.

Each vehicle has a capacity, current location, availability window,
cost per km, and an active flag.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Vehicle(Base):
    """A transport vehicle available for carrying harvests.

    Vehicles are filtered by capacity, location proximity, availability window,
    and ability to meet time limits during the optimization step.
    """

    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity_kg: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Maximum load capacity in kilograms"
    )
    current_location_lat: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Current latitude"
    )
    current_location_lng: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Current longitude"
    )
    available_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Earliest availability time"
    )
    available_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Latest availability time (null = no limit)"
    )
    cost_per_km_idr: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Operating cost per kilometer in IDR"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Vehicle(name={self.name!r}, capacity={self.capacity_kg}kg)>"
