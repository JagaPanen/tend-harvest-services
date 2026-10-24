"""Org / guest scenario access helpers."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.models.scenario import Scenario


def org_filter(column, principal: Principal):
    return column == principal.org_id


def apply_scenario_visibility(stmt: Select, principal: Principal) -> Select:
    """Users see org scenarios that are not guest clones; guests see only their clone."""
    stmt = stmt.where(Scenario.organization_id == principal.org_id)
    if principal.is_guest:
        if principal.session_id is None:
            raise HTTPException(status_code=401, detail="Guest session missing")
        return stmt.where(Scenario.guest_session_id == principal.session_id)
    return stmt.where(Scenario.guest_session_id.is_(None))


async def get_org_scenario(
    db: AsyncSession,
    scenario_id: uuid.UUID,
    principal: Principal,
) -> Scenario:
    stmt = apply_scenario_visibility(
        select(Scenario).where(Scenario.id == scenario_id), principal
    )
    result = await db.execute(stmt)
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    if scenario.is_template and principal.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot mutate the shared demo template",
        )
    return scenario
