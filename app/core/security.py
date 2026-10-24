"""Password hashing and JWT helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.core.config import settings

Role = Literal["user", "guest"]


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, rounds_s, salt, digest_hex = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def hash_ip(ip: str | None) -> str:
    raw = (ip or "unknown").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_access_token(
    *,
    role: Role,
    org_id: uuid.UUID,
    subject: str,
    session_id: uuid.UUID | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    hours = settings.guest_jwt_expire_hours if role == "guest" else settings.jwt_expire_hours
    expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "org_id": str(org_id),
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    if session_id is not None:
        payload["session_id"] = str(session_id)
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
