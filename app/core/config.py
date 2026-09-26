"""Harvest Expedition — Application configuration.

All settings are loaded from environment variables with sensible defaults.
Optimization weights are stored here so they're version-controlled and reproducible.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Database ──
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/harvest_expedition",
        description="Async database connection string",
    )
    database_url_sync: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/harvest_expedition",
        description="Sync database connection string (for Alembic)",
    )

    # ── Mapbox ──
    mapbox_access_token: str = Field(
        default="",
        description="Mapbox API access token for routing",
    )

    # ── Optimization weights (α, β, γ) ──
    alpha_travel_cost: float = Field(default=0.4, description="Weight for travel cost")
    beta_detour_cost: float = Field(default=0.3, description="Weight for detour cost")
    gamma_spoilage_risk: float = Field(default=0.3, description="Weight for spoilage risk")

    # ── Server ──
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    debug: bool = Field(default=False, description="Enable debug mode")

    # ── Currency & Units ──
    default_currency: str = Field(default="IDR", description="Default currency")
    default_volume_unit: str = Field(default="kg", description="Default volume unit")
    cost_per_km_idr: float = Field(default=5000.0, description="Default transport cost per km in IDR")

    # ── Risk formula version ──
    risk_formula_version: str = Field(
        default="v1.0.0",
        description="Current risk formula version for reproducibility tracking",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton settings instance
settings = Settings()
