from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.db.session import get_db
from app.models import UserProfile
from app.models.user import User
from app.schemas.user_profile import (
    UserProfileCreate,
    UserProfileResponse,
    UserProfileUpdate,
)

router = APIRouter(prefix="/user-profiles", tags=["User Profiles"])


async def _get_profile_or_404(db: AsyncSession, user_id: UUID) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )
    return profile


@router.post("/", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_user_profile(
    payload: UserProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile already exists.",
        )

    profile = UserProfile(**payload.model_dump(), user_id=current_user.id)
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User profile already exists or references an invalid user.",
        )

    await db.refresh(profile)
    return profile


@router.get("/me", response_model=UserProfileResponse)
async def get_my_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_profile_or_404(db, current_user.id)


@router.put("/me", response_model=UserProfileResponse)
async def update_my_user_profile(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await _get_profile_or_404(db, current_user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await _get_profile_or_404(db, user_id)


@router.put("/{user_id}", response_model=UserProfileResponse)
async def update_user_profile_by_id(
    user_id: UUID,
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    profile = await _get_profile_or_404(db, user_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile
