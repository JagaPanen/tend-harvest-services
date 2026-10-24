"""FastAPI auth dependency — user or guest JWT principal."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)

Role = Literal["user", "guest"]


@dataclass(frozen=True)
class Principal:
    role: Role
    org_id: uuid.UUID
    subject: str
    session_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None

    @property
    def is_guest(self) -> bool:
        return self.role == "guest"


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        role = payload.get("role")
        org_raw = payload.get("org_id")
        subject = payload.get("sub")
        if role not in ("user", "guest") or not org_raw or not subject:
            raise ValueError("incomplete token")
        session_id = None
        if payload.get("session_id"):
            session_id = uuid.UUID(str(payload["session_id"]))
        user_id = None
        if role == "user":
            user_id = uuid.UUID(str(subject))
        return Principal(
            role=role,  # type: ignore[arg-type]
            org_id=uuid.UUID(str(org_raw)),
            subject=str(subject),
            session_id=session_id,
            user_id=user_id,
        )
    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
