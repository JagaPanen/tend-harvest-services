"""Seed data for the commodities table.

Contains representative commodities for each of the 5 perishability classes (A–E).
Shelf-life figures are estimated from agricultural literature for standard ambient
conditions in tropical climates (28–32°C, ~70% RH).

Sources to validate against:
- FAO Post-Harvest Operations INPhO
- USDA Handbook 66 (Commercial Storage)
- Indonesia's BPTP/Kementan commodity sheets
"""

COMMODITY_SEEDS: list[dict] = [
    # ─── Class A: Highly Perishable (≤24 h ambient) ───
    {
        "name": "Tomato",
        "perishability_class": "A",
        "shelf_life_hours": 18.0,
        "default_price_idr_per_kg": 15000.0,
    },
    {
        "name": "Leafy Greens (Spinach/Kangkung)",
        "perishability_class": "A",
        "shelf_life_hours": 12.0,
        "default_price_idr_per_kg": 12000.0,
    },
    {
        "name": "Strawberry",
        "perishability_class": "A",
        "shelf_life_hours": 16.0,
        "default_price_idr_per_kg": 60000.0,
    },
    # ─── Class B: Perishable (24–48 h ambient) ───
    {
        "name": "Chili (Cabai Rawit)",
        "perishability_class": "B",
        "shelf_life_hours": 36.0,
        "default_price_idr_per_kg": 40000.0,
    },
    {
        "name": "Grape",
        "perishability_class": "B",
        "shelf_life_hours": 30.0,
        "default_price_idr_per_kg": 55000.0,
    },
    {
        "name": "Bell Pepper (Paprika)",
        "perishability_class": "B",
        "shelf_life_hours": 40.0,
        "default_price_idr_per_kg": 35000.0,
    },
    # ─── Class C: Moderate (2–7 days ambient) ───
    {
        "name": "Banana",
        "perishability_class": "C",
        "shelf_life_hours": 96.0,
        "default_price_idr_per_kg": 12000.0,
    },
    {
        "name": "Mango",
        "perishability_class": "C",
        "shelf_life_hours": 72.0,
        "default_price_idr_per_kg": 20000.0,
    },
    {
        "name": "Cabbage (Kubis)",
        "perishability_class": "C",
        "shelf_life_hours": 120.0,
        "default_price_idr_per_kg": 8000.0,
    },
    # ─── Class D: Semi-Durable (1–4 weeks ambient) ───
    {
        "name": "Potato",
        "perishability_class": "D",
        "shelf_life_hours": 480.0,
        "default_price_idr_per_kg": 14000.0,
    },
    {
        "name": "Onion (Bawang Merah)",
        "perishability_class": "D",
        "shelf_life_hours": 360.0,
        "default_price_idr_per_kg": 35000.0,
    },
    {
        "name": "Carrot",
        "perishability_class": "D",
        "shelf_life_hours": 336.0,
        "default_price_idr_per_kg": 15000.0,
    },
    # ─── Class E: Long-Lasting (>1 month ambient) ───
    {
        "name": "Rice (Beras)",
        "perishability_class": "E",
        "shelf_life_hours": 4320.0,
        "default_price_idr_per_kg": 13000.0,
    },
    {
        "name": "Dried Corn (Jagung Pipil)",
        "perishability_class": "E",
        "shelf_life_hours": 2160.0,
        "default_price_idr_per_kg": 6000.0,
    },
    {
        "name": "Soybean (Kedelai)",
        "perishability_class": "E",
        "shelf_life_hours": 2880.0,
        "default_price_idr_per_kg": 11000.0,
    },
]
