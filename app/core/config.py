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
        default="postgresql+asyncpg://username:password@localhost:5432/harvest_expedition",
        description="Async database connection string",
    )
    database_url_sync: str = Field(
        default="postgresql://username:password@localhost:5432/harvest_expedition",
        description="Sync database connection string (for Alembic)",
    )

    # ── Mapbox / OSRM ──
    mapbox_access_token: str = Field(
        default="",
        description="Mapbox API access token for routing (preferred when set)",
    )
    osrm_base_url: str = Field(
        default="https://router.project-osrm.org",
        description="OSRM base URL used when Mapbox token is missing or fails",
    )

    # ── Optimization weights (α, β, γ) ──
    alpha_travel_cost: float = Field(default=0.4, description="Weight for travel cost")
    beta_detour_cost: float = Field(default=0.3, description="Weight for detour cost")
    gamma_spoilage_risk: float = Field(
        default=0.3, description="Weight for spoilage risk"
    )

    # ── Server ──
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8009, description="API server port")
    api_prefix: str = Field(
        default="/api",
        description="Public API prefix. Matches the frontend base URL path, with no version segment.",
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # ── Currency & Units ──
    default_currency: str = Field(default="IDR", description="Default currency")
    default_volume_unit: str = Field(default="kg", description="Default volume unit")
    cost_per_km_idr: float = Field(
        default=5000.0, description="Default transport cost per km in IDR"
    )

    # ── Risk formula version ──
    risk_formula_version: str = Field(
        default="v1.0.0",
        description="Current risk formula version for reproducibility tracking",
    )

    # ── Auth / guest demo (P0) ──
    jwt_secret: str = Field(
        default="jagapanen-dev-secret-change-me",
        description="HMAC secret for JWT access tokens",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_expire_hours: int = Field(default=72, description="User JWT TTL in hours")
    guest_jwt_expire_hours: int = Field(default=2, description="Guest JWT TTL in hours")
    guest_max_optimize_runs: int = Field(
        default=5, description="Max POST /optimization/run per guest demo session"
    )

    # ── Billing / plans (P4) ──
    pilot_max_optimize_runs: int = Field(
        default=25, description="Max optimize runs during Free Pilot"
    )
    pilot_days: int = Field(default=14, description="Pilot trial length in days")
    starter_max_optimize_runs: int = Field(
        default=200, description="Max optimize runs per calendar month on Starter"
    )
    fleet_max_optimize_runs: int = Field(
        default=1000, description="Max optimize runs per calendar month on Fleet"
    )
    usage_soft_cap_ratio: float = Field(
        default=0.8, description="Soft banner threshold as fraction of plan run limit"
    )
    billing_stub: bool = Field(
        default=True,
        description="When true (or Xendit key empty), checkout is stubbed; webhook still works",
    )
    xendit_secret_key: str = Field(
        default="", description="Xendit secret key; empty → stub checkout"
    )
    xendit_webhook_token: str = Field(
        default="",
        description="Optional Xendit callback verification token (x-callback-token)",
    )
    billing_public_app_url: str = Field(
        default="http://127.0.0.1:3000",
        description="FE origin used for stub checkout redirect URLs",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton settings instance
settings = Settings()
