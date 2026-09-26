# Harvest Expedition — Backend API

**Risk-Based Post-Harvest Distribution Optimization System**

A decision-support system that helps agricultural cooperatives decide which vehicle
should carry which harvest, and via which route — taking commodity spoilage risk into
account rather than just distance or travel time.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI + Python 3.11+ |
| ORM / Validation | SQLAlchemy 2.0 (async) + Pydantic v2 |
| Database | PostgreSQL (via asyncpg) |
| Optimization | Google OR-Tools |
| Routing | Mapbox Directions API (OSRM fallback) |
| Testing | pytest + pytest-asyncio |

## Quick Start

```bash
# 1. Setup virtual environment and install dependencies
cd apps/api
python -m venv .venv

# Activate it (Windows):
.venv\Scripts\activate
# Activate it (Linux/macOS):
# source .venv/bin/activate

pip install -e ".[dev]"

# 2. Copy env and configure
cp .env.example .env

# 3. Run database migrations
alembic upgrade head

# 4. Seed demo data
python -m app.seed

# 5. Start the server
uvicorn app.main:app --reload
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/scenarios` | Create a planning scenario |
| POST | `/api/v1/scenarios/{id}/harvests` | Add harvest inputs |
| GET | `/api/v1/commodities` | List commodity classes |
| GET | `/api/v1/vehicles` | List available vehicles |
| POST | `/api/v1/risk/score` | Calculate spoilage risk |
| POST | `/api/v1/optimization/preview` | Run feasibility checks |
| POST | `/api/v1/optimization/run` | Generate recommendations |
| GET | `/api/v1/optimization/runs/{id}` | Retrieve saved run |
| GET | `/api/v1/optimization/runs/{id}/comparison` | Baseline vs system |

## Project Structure

```
apps/api/
├── app/
│   ├── api/v1/           # Route handlers
│   ├── core/             # Config, database, dependencies
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   └── services/         # Business logic
│       ├── risk/         # Spoilage risk scoring
│       ├── optimization/ # OR-Tools, consolidation
│       └── routing/      # Mapbox/OSRM adapter
├── infra/
│   ├── migrations/       # Alembic migrations
│   └── seed/             # Demo data
└── tests/
    ├── fixtures/         # Locked baseline scenario
    ├── unit/             # Unit tests
    └── integration/      # API integration tests
```

## Risk Scoring Formula

```
Risk Score = min(100, 100 × [(Time Since Harvest + Estimated Transit Time) / Shelf Life Reference] × Handling Factor)
```

Commodities are classified into 5 vulnerability classes:
- **A** — Highly perishable (e.g., tomatoes, leafy greens)
- **B** — Perishable (e.g., chilies, berries)
- **C** — Moderate (e.g., bananas, mangoes)
- **D** — Semi-durable (e.g., potatoes, onions)
- **E** — Long-lasting (e.g., rice, dried goods)

## Optimization Modes

| Mode | α (Travel) | β (Detour) | γ (Spoilage) |
|------|-----------|-----------|--------------|
| Cost Priority | 0.6 | 0.3 | 0.1 |
| Balanced | 0.4 | 0.3 | 0.3 |
| Spoilage Priority | 0.1 | 0.2 | 0.7 |

## License

This project is licensed under the MIT License.
