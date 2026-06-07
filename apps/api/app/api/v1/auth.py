from datetime import datetime, timedelta, timezone
import json
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limiter import limiter
from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, create_refresh_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.daily_recommendation_service import invalidate_user_plan_cache

router = APIRouter(prefix="/auth", tags=["Auth"])

# Atomic token rotation: SET NX with TTL, returns 1 if key was set (token not yet used), 0 if already exists.
LUA_ROTATE = """
local result = redis.call('SET', KEYS[1], '1', 'NX', 'EX', ARGV[1])
if result then
  return 1
else
  return 0
end
"""
# TTL for used-refresh keys matches refresh token lifetime (7 days in seconds).
ROTATE_TTL = 7 * 24 * 3600


@router.post("/login")
@limiter.limit("10/minute")
async def login_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if user and user.login_allowed_at and user.login_allowed_at > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
        )

    if not user or not verify_password(form_data.password, user.password_hash):
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= 5:
                user.login_allowed_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active.",
        )

    user.failed_login_attempts = 0
    user.login_allowed_at = datetime.now(timezone.utc)
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(user.id, expires_delta=expires_delta)
    refresh_token = create_refresh_token(str(user.id))

    response = Response(
        content=json.dumps({
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }),
        media_type="application/json",
    )
    response.set_cookie(
        key="smartmeal_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 3600,
        path="/api/auth/refresh",
    )
    return response


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_user(
    request: Request,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists.",
        )

    user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role="user",
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists.",
        )

    await db.refresh(user)
    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the current user's profile. Only full_name can be updated here.
    For extended profile data (age, gender, health conditions, etc.) use the
    /api/v1/profiles endpoint.
    """
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not update user profile.",
        )

    await invalidate_user_plan_cache(current_user.id)
    await db.refresh(current_user)
    return current_user


@router.post("/refresh")
@limiter.limit("30/minute")
async def refresh_access_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None, alias="smartmeal_refresh_token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token (from httpOnly cookie) for a new access token.
    Refresh token rotation: a used refresh token is immediately invalidated
    to prevent replay attacks.
    """
    from jose import JWTError as JoseJWTError
    from app.core.cache import get_redis

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided.",
        )

    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
            )
        user_id = payload.get("sub")
        jti = payload.get("jti")
        if not user_id or not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )
    except JoseJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    # Atomic rotation: try to mark token as used. Deny (503) if Redis is unavailable.
    try:
        redis = await get_redis()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        )
    try:
        acquired = await redis.eval(LUA_ROTATE, 1, f"used_refresh:{jti}", ROTATE_TTL)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        )
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has already been used.",
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    # Issue new tokens
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(user.id, expires_delta=expires_delta)
    new_refresh_token = create_refresh_token(str(user.id))

    response = Response(
        content=json.dumps({
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }),
        media_type="application/json",
    )
    response.set_cookie(
        key="smartmeal_refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 3600,
        path="/api/auth/refresh",
    )
    return response


@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Clear the refresh token cookie and revoke it in Redis using the token's jti.
    Clears the cookie regardless of Redis availability (client-side protection always works).
    """
    import logging
    logger = logging.getLogger(__name__)

    refresh_token = request.cookies.get("smartmeal_refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[ALGORITHM],
            )
            jti = payload.get("jti")
            if jti:
                redis = await get_redis()
                await redis.setex(f"used_refresh:{jti}", ROTATE_TTL, "1")
        except Exception:
            logger.warning("logout: failed to revoke refresh token in Redis (degraded — cookie still cleared)")

    response = Response(content=json.dumps({"message": "Logged out"}), media_type="application/json")
    response.delete_cookie(
        key="smartmeal_refresh_token",
        path="/api/auth/refresh",
    )
    return response
