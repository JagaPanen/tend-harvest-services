"""Seed data for the vehicles table.

Demo vehicles located around West Java (Bandung area) — a major
agricultural region in Indonesia. Two vehicle sizes as per the PRD demo case:
a 500 kg pickup and a 1,000 kg truck, plus extras for realism.
"""

from datetime import datetime, timezone

VEHICLE_SEEDS: list[dict] = [
    {
        "name": "Pickup Truck 500kg (Bandung)",
        "capacity_kg": 500.0,
        "current_location_lat": -6.9175,
        "current_location_lng": 107.6191,
        "available_from": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "cost_per_km_idr": 4500.0,
    },
    {
        "name": "Box Truck 1000kg (Lembang)",
        "capacity_kg": 1000.0,
        "current_location_lat": -6.8118,
        "current_location_lng": 107.6176,
        "available_from": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "cost_per_km_idr": 6000.0,
    },
    {
        "name": "Pickup Truck 600kg (Garut)",
        "capacity_kg": 600.0,
        "current_location_lat": -7.2108,
        "current_location_lng": 107.9089,
        "available_from": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "cost_per_km_idr": 5000.0,
    },
    {
        "name": "Box Truck 1500kg (Subang)",
        "capacity_kg": 1500.0,
        "current_location_lat": -6.5714,
        "current_location_lng": 107.7542,
        "available_from": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "cost_per_km_idr": 7500.0,
    },
    {
        "name": "Small Van 300kg (Cianjur)",
        "capacity_kg": 300.0,
        "current_location_lat": -6.8197,
        "current_location_lng": 107.1419,
        "available_from": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "cost_per_km_idr": 3500.0,
    },
]
