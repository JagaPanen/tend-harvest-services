"""Seed data for the locked demo scenario.

Scenario: "Bandung Morning Harvest"
- Harvest A: 300kg Tomatoes (Class A, highly perishable)
- Harvest B: 200kg Chilies (Class B, perishable)
- Harvest C: 400kg Potatoes (Class D, semi-durable)

Vehicles:
- Vehicle 1: 500kg capacity
- Vehicle 2: 1000kg capacity

The system should be able to explain why A+B are consolidated but A+C are not.
"""

from datetime import datetime, timezone, timedelta
import uuid

# We will generate static UUIDs so the seed data is deterministic
SCENARIO_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
HARVEST_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
HARVEST_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
HARVEST_C_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

now = datetime.now(timezone.utc)

DEMO_SCENARIO = {
    "id": SCENARIO_ID,
    "name": "Bandung Morning Harvest",
    "status": "draft",
    "optimization_mode": "balanced",
}

# The commodity names should match those in commodities.py
DEMO_HARVESTS = [
    {
        "id": HARVEST_A_ID,
        "scenario_id": SCENARIO_ID,
        "commodity_name": "Tomato",
        "label": "Harvest A (Tomato)",
        "location_lat": -6.85,
        "location_lng": 107.55,
        "destination_lat": -6.92,
        "destination_lng": 107.61,
        "destination_name": "Pasar Induk Caringin",
        "volume_kg": 300.0,
        "harvested_at": now - timedelta(hours=9),  # 9h since harvest
        "handling_factor": 1.0,
    },
    {
        "id": HARVEST_B_ID,
        "scenario_id": SCENARIO_ID,
        "commodity_name": "Chili (Cabai Rawit)",
        "label": "Harvest B (Chili)",
        "location_lat": -6.86,
        "location_lng": 107.56,
        "destination_lat": -6.92,
        "destination_lng": 107.61,
        "destination_name": "Pasar Induk Caringin",
        "volume_kg": 200.0,
        "harvested_at": now - timedelta(hours=5),
        "handling_factor": 1.0,
    },
    {
        "id": HARVEST_C_ID,
        "scenario_id": SCENARIO_ID,
        "commodity_name": "Potato",
        "label": "Harvest C (Potato)",
        "location_lat": -6.84,
        "location_lng": 107.54,
        "destination_lat": -6.93,
        "destination_lng": 107.62,
        "destination_name": "Pasar Induk Gedebage",
        "volume_kg": 400.0,
        "harvested_at": now - timedelta(hours=2),
        "handling_factor": 1.0,
    },
]
