"""Harvest Expedition — FastAPI application entry point."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.commodities import router as commodities_router
from app.api.v1.harvests import router as harvests_router
from app.api.v1.optimization import router as optimization_router
from app.api.v1.risk import router as risk_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.vehicles import router as vehicles_router
from app.core.config import settings

app = FastAPI(
    title="Harvest Expedition API",
    description=(
        "Risk-Based Post-Harvest Distribution Optimization System. "
        "Helps agricultural cooperatives decide which vehicle should carry which harvest, "
        "and via which route — taking commodity spoilage risk into account."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow the Next.js frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API v1 routes ──
app.include_router(commodities_router, prefix="/api/v1")
app.include_router(vehicles_router, prefix="/api/v1")
app.include_router(scenarios_router, prefix="/api/v1")
app.include_router(harvests_router, prefix="/api/v1")
app.include_router(optimization_router, prefix="/api/v1")
app.include_router(risk_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "risk_formula_version": settings.risk_formula_version,
    }
