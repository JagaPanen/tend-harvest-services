"""Database seeder — demo org + catalog + template scenario.

Run: python -m app.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.database import Base, async_session_factory, engine
from app.models.commodity import Commodity
from app.models.harvest import Harvest
from app.models.organization import DEMO_ORG_ID, Organization
from app.models.scenario import Scenario
from app.models.vehicle import Vehicle
from infra.seed.commodities import COMMODITY_SEEDS
from infra.seed.scenarios import DEMO_HARVESTS, DEMO_SCENARIO
from infra.seed.vehicles import VEHICLE_SEEDS


async def seed_demo_org() -> bool:
    async with async_session_factory() as session:
        existing = await session.get(Organization, DEMO_ORG_ID)
        if existing is not None:
            return False
        session.add(
            Organization(
                id=DEMO_ORG_ID,
                name="JagaPanen Demo",
                is_demo=True,
                plan="guest",
            )
        )
        await session.commit()
        return True


async def seed_commodities() -> int:
    count = 0
    async with async_session_factory() as session:
        for data in COMMODITY_SEEDS:
            result = await session.execute(
                select(Commodity).where(
                    Commodity.organization_id == DEMO_ORG_ID,
                    Commodity.name == data["name"],
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(Commodity(**data, organization_id=DEMO_ORG_ID))
                count += 1
        await session.commit()
    return count


async def seed_vehicles() -> int:
    count = 0
    async with async_session_factory() as session:
        for data in VEHICLE_SEEDS:
            result = await session.execute(
                select(Vehicle).where(
                    Vehicle.organization_id == DEMO_ORG_ID,
                    Vehicle.name == data["name"],
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(Vehicle(**data, organization_id=DEMO_ORG_ID))
                count += 1
        await session.commit()
    return count


async def seed_scenarios() -> int:
    count = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(Scenario).where(Scenario.id == DEMO_SCENARIO["id"])
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            # Ensure template flags for upgraded DBs
            existing.organization_id = DEMO_ORG_ID
            existing.is_template = True
            existing.guest_session_id = None
            await session.commit()
            return 0

        scenario = Scenario(
            **DEMO_SCENARIO,
            organization_id=DEMO_ORG_ID,
            is_template=True,
            guest_session_id=None,
        )
        session.add(scenario)
        await session.flush()

        comm_names = {h["commodity_name"] for h in DEMO_HARVESTS}
        comm_result = await session.execute(
            select(Commodity).where(
                Commodity.organization_id == DEMO_ORG_ID,
                Commodity.name.in_(comm_names),
            )
        )
        comm_map = {c.name: c.id for c in comm_result.scalars().all()}

        for h_data in DEMO_HARVESTS:
            data = h_data.copy()
            name = data.pop("commodity_name")
            data["commodity_id"] = comm_map[name]
            session.add(Harvest(**data))

        count += 1
        await session.commit()
    return count


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("🏢 Seeding demo organization...")
    created = await seed_demo_org()
    print(f"   → {'Created' if created else 'Exists'} org_demo {DEMO_ORG_ID}")

    print("🌱 Seeding commodities...")
    n = await seed_commodities()
    print(f"   → Inserted {n} new commodities")

    print("🚛 Seeding vehicles...")
    n = await seed_vehicles()
    print(f"   → Inserted {n} new vehicles")

    print("📋 Seeding demo template scenario...")
    n = await seed_scenarios()
    print(f"   → Inserted {n} new scenarios")

    print("✅ Seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
