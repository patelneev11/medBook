import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.user import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UsageResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

_PLACEHOLDER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _placeholder_user(email: str = "user@example.com", full_name: str = "John Doe") -> UserResponse:
    return UserResponse(
        id=_PLACEHOLDER_ID,
        email=email,
        full_name=full_name,
        is_active=True,
        is_verified=True,
        role="member",
        created_at=_now(),
    )


# ── Auth (/auth) ──────────────────────────────────────────────────────────────

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    # TODO: hash password, save to DB, check for duplicate email — Session 4
    return _placeholder_user(email=payload.email, full_name=payload.full_name)


@auth_router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    # TODO: verify credentials, issue real JWTs — Session 4
    return TokenResponse(
        access_token="placeholder-access-token",
        refresh_token="placeholder-refresh-token",
    )


@auth_router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(payload: RefreshRequest):
    # TODO: validate refresh token, issue new access token — Session 4
    return AccessTokenResponse(access_token="placeholder-access-token")


@auth_router.post("/logout")
async def logout():
    # TODO: blacklist token in Redis or DB — Session 4
    return {"message": "logged out"}


# ── Users (/users) ────────────────────────────────────────────────────────────

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/me", response_model=UserResponse)
async def get_me(db: AsyncSession = Depends(get_db)):
    # TODO: extract user from JWT, load from DB — Session 4
    return _placeholder_user()


@users_router.patch("/me", response_model=UserResponse)
async def update_me(payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    # TODO: update authenticated user in DB — Session 4
    return _placeholder_user(full_name=payload.full_name or "John Doe")


@users_router.get("/me/usage", response_model=UsageResponse)
async def get_usage(db: AsyncSession = Depends(get_db)):
    # TODO: query real counts — Session 4
    return UsageResponse(documents_count=0, queries_this_month=0, storage_used_bytes=0)
