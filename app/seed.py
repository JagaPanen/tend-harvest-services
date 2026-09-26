"""Database seeder — populates initial reference data.

Run: python -m app.seed
"""

import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory, engine, Base
from app.models.commodity import Commodity
from app.models.harvest import Harvest
from app.models.scenario import Scenario
from app.models.vehicle import Vehicle
from infra.seed.commodities import COMMODITY_SEEDS
from infra.seed.scenarios import DEMO_HARVESTS, DEMO_SCENARIO
from infra.seed.vehicles import VEHICLE_SEEDS


async def seed_commodities() -> int:
    """Insert commodity seed data if not already present."""
    count = 0
    async with async_session_factory() as session:
        for data in COMMODITY_SEEDS:
            result = await session.execute(
                select(Commodity).where(Commodity.name == data["name"])
            )
            if result.scalar_one_or_none() is None:
                session.add(Commodity(**data))
                count += 1
        await session.commit()
    return count


async def seed_vehicles() -> int:
    """Insert vehicle seed data if not already present."""
    count = 0
    async with async_session_factory() as session:
        for data in VEHICLE_SEEDS:
            result = await session.execute(
                select(Vehicle).where(Vehicle.name == data["name"])
            )
            if result.scalar_one_or_none() is None:
                session.add(Vehicle(**data))
                count += 1
        await session.commit()
    return count


async def seed_scenarios() -> int:
    """Insert the demo scenario and harvests if not already present."""
    count = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(Scenario).where(Scenario.id == DEMO_SCENARIO["id"])
        )
        if result.scalar_one_or_none() is None:
            # Create scenario
            scenario = Scenario(**DEMO_SCENARIO)
            session.add(scenario)
            await session.flush()
            
            # Fetch commodities for foreign keys
            comm_names = {h["commodity_name"] for h in DEMO_HARVESTS}
            comm_result = await session.execute(
                select(Commodity).where(Commodity.name.in_(comm_names))
            )
            comm_map = {c.name: c.id for c in comm_result.scalars().all()}
            
            # Create harvests
            for h_data in DEMO_HARVESTS:
                data = h_data.copy()
                name = data.pop("commodity_name")
                data["commodity_id"] = comm_map[name]
                session.add(Harvest(**data))
            
            count += 1
            await session.commit()
    return count


async def main() -> None:
    """Run all seeders."""
    # Create tables if they don't exist (for dev convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("🌱 Seeding commodities...")
    n = await seed_commodities()
    print(f"   → Inserted {n} new commodities")

    print("🚛 Seeding vehicles...")
    n = await seed_vehicles()
    print(f"   → Inserted {n} new vehicles")
    
    print("📋 Seeding demo scenario...")
    n = await seed_scenarios()
    print(f"   → Inserted {n} new scenarios")

    print("✅ Seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
