"""Auth endpoints — signup, login, guest demo-session."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_ip, hash_password, verify_password
from app.models.commodity import Commodity
from app.models.organization import DEMO_ORG_ID, Membership, MembershipRole, Organization, User, DemoSession
from app.models.vehicle import Vehicle
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.services.demo_clone import clone_template_for_guest

router = APIRouter(prefix="/auth", tags=["Auth"])


async def _copy_demo_catalog(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Give new orgs a starter commodity + vehicle catalog cloned from demo."""
    demo_commodities = (
        await db.execute(select(Commodity).where(Commodity.organization_id == DEMO_ORG_ID))
    ).scalars().all()
    for c in demo_commodities:
        db.add(
            Commodity(
                organization_id=org_id,
                name=c.name,
                perishability_class=c.perishability_class,
                shelf_life_hours=c.shelf_life_hours,
                default_price_idr_per_kg=c.default_price_idr_per_kg,
                active=c.active,
            )
        )
    demo_vehicles = (
        await db.execute(select(Vehicle).where(Vehicle.organization_id == DEMO_ORG_ID))
    ).scalars().all()
    for v in demo_vehicles:
        db.add(
            Vehicle(
                organization_id=org_id,
                name=v.name,
                capacity_kg=v.capacity_kg,
                current_location_lat=v.current_location_lat,
                current_location_lng=v.current_location_lng,
                available_from=v.available_from,
                available_until=v.available_until,
                cost_per_km_idr=v.cost_per_km_idr,
                active=v.active,
            )
        )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    now = datetime.now(timezone.utc)
    org = Organization(
        name=payload.organization_name,
        is_demo=False,
        plan="pilot",
        pilot_ends_at=now + timedelta(days=settings.pilot_days),
    )
    db.add(org)
    await db.flush()

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name or payload.email.split("@")[0],
        organization_id=org.id,
    )
    db.add(user)
    await db.flush()
    db.add(
        Membership(
            organization_id=org.id,
            user_id=user.id,
            role=MembershipRole.OWNER.value,
        )
    )
    await _copy_demo_catalog(db, org.id)
    from app.models.billing import UsageCounter

    db.add(
        UsageCounter(
            organization_id=org.id,
            period_key="pilot",
            optimize_runs_used=0,
        )
    )
    await db.flush()

    token, expires_at = create_access_token(
        role="user", org_id=org.id, subject=str(user.id)
    )
    return TokenResponse(
        access_token=token,
        role="user",
        org_id=org.id,
        expires_at=expires_at,
        user_id=user.id,
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token, expires_at = create_access_token(
        role="user", org_id=user.organization_id, subject=str(user.id)
    )
    return TokenResponse(
        access_token=token,
        role="user",
        org_id=user.organization_id,
        expires_at=expires_at,
        user_id=user.id,
        email=user.email,
    )


@router.post("/demo-session", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_demo_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Issue a guest JWT and clone the seeded template scenario (no email)."""
    org = await db.get(Organization, DEMO_ORG_ID)
    if org is None or not org.is_demo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo organization is not seeded. Run: python -m app.seed",
        )

    session_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.guest_jwt_expire_hours)
    try:
        clone = await clone_template_for_guest(db, guest_session_id=session_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    client_ip = request.client.host if request.client else None
    demo = DemoSession(
        id=session_id,
        organization_id=DEMO_ORG_ID,
        scenario_id=clone.id,
        ip_hash=hash_ip(client_ip),
        runs_used=0,
        expires_at=expires_at,
    )
    db.add(demo)
    await db.flush()

    token, token_exp = create_access_token(
        role="guest",
        org_id=DEMO_ORG_ID,
        subject=f"guest:{session_id}",
        session_id=session_id,
    )
    return TokenResponse(
        access_token=token,
        role="guest",
        org_id=DEMO_ORG_ID,
        expires_at=token_exp,
        scenario_id=clone.id,
        runs_used=0,
        runs_remaining=settings.guest_max_optimize_runs,
    )


@router.get("/me", response_model=TokenResponse)
async def me(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Return principal metadata; guests include run quota."""
    if principal.is_guest:
        if principal.session_id is None:
            raise HTTPException(status_code=401, detail="Invalid guest session")
        demo = await db.get(DemoSession, principal.session_id)
        if demo is None:
            raise HTTPException(status_code=401, detail="Guest session not found")
        remaining = max(0, settings.guest_max_optimize_runs - demo.runs_used)
        # Re-issue is not needed; echo current token fields without rotating.
        # Client already holds the token; this endpoint is informational.
        dummy_token = "use-existing"
        return TokenResponse(
            access_token=dummy_token,
            role="guest",
            org_id=principal.org_id,
            expires_at=demo.expires_at,
            scenario_id=demo.scenario_id,
            runs_used=demo.runs_used,
            runs_remaining=remaining,
        )

    user = await db.get(User, principal.user_id) if principal.user_id else None
    _, expires_at = create_access_token(
        role="user", org_id=principal.org_id, subject=principal.subject
    )
    return TokenResponse(
        access_token="use-existing",
        role="user",
        org_id=principal.org_id,
        expires_at=expires_at,
        user_id=principal.user_id,
        email=user.email if user else None,
    )
