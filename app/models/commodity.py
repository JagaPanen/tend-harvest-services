"""Commodity model — represents agricultural commodity types with perishability classification.

Each commodity has a perishability class (A–E), shelf-life reference hours,
and a default price used for economic impact calculations.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Commodity(Base):
    """An agricultural commodity type with spoilage characteristics.

    Perishability classes:
        A — Highly perishable (e.g., tomatoes, leafy greens)
        B — Perishable (e.g., chilies, berries)
        C — Moderate (e.g., bananas, mangoes)
        D — Semi-durable (e.g., potatoes, onions)
        E — Long-lasting (e.g., rice, dried goods)
    """

    __tablename__ = "commodities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    perishability_class: Mapped[str] = mapped_column(
        String(1), nullable=False, comment="A (most perishable) to E (least perishable)"
    )
    shelf_life_hours: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Estimated shelf life under standard conditions (hours)"
    )
    default_price_idr_per_kg: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Default commodity price in IDR per kg"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    harvests: Mapped[list["Harvest"]] = relationship(  # noqa: F821
        back_populates="commodity", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<Commodity(name={self.name!r}, class={self.perishability_class}, "
            f"shelf_life={self.shelf_life_hours}h)>"
        )
