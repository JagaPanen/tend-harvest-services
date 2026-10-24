"""Best-effort ALTER for existing Docker volumes (create_all won't add columns)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def ensure_billing_columns(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            """
            ALTER TABLE organizations
            ADD COLUMN IF NOT EXISTS pilot_ends_at TIMESTAMPTZ NULL
            """
        )
    )
