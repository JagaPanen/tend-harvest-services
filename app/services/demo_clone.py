"""Clone the demo template scenario for a guest session."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.harvest import Harvest
from app.models.scenario import Scenario, ScenarioStatus
from app.models.organization import DEMO_ORG_ID


async def get_template_scenario(db: AsyncSession) -> Scenario | None:
    result = await db.execute(
        select(Scenario)
        .where(
            Scenario.organization_id == DEMO_ORG_ID,
            Scenario.is_template.is_(True),
        )
        .options(selectinload(Scenario.harvests))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def clone_template_for_guest(
    db: AsyncSession,
    *,
    guest_session_id: uuid.UUID,
) -> Scenario:
    template = await get_template_scenario(db)
    if template is None:
        raise LookupError("Demo template scenario is not seeded")

    clone = Scenario(
        name=f"Guest · {template.name}",
        status=ScenarioStatus.DRAFT,
        optimization_mode=template.optimization_mode,
        organization_id=DEMO_ORG_ID,
        is_template=False,
        guest_session_id=guest_session_id,
    )
    db.add(clone)
    await db.flush()

    for h in template.harvests:
        db.add(
            Harvest(
                scenario_id=clone.id,
                commodity_id=h.commodity_id,
                label=h.label,
                location_lat=h.location_lat,
                location_lng=h.location_lng,
                volume_kg=h.volume_kg,
                harvested_at=h.harvested_at,
                destination_lat=h.destination_lat,
                destination_lng=h.destination_lng,
                destination_name=h.destination_name,
                handling_factor=h.handling_factor,
            )
        )
    await db.flush()
    await db.refresh(clone)
    return clone
