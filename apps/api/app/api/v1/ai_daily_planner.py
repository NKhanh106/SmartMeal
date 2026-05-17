from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.daily_recommendation import (
    DailyRecommendationResponse,
    GenerateDailyPlannerResponse,
)
from app.services.daily_recommendation_service import (
    generate_daily_recommendation,
    get_recommendation_by_date,
)

router = APIRouter(prefix="/ai/daily-planner", tags=["AI Daily Planner"])


@router.post("/generate/{user_id}", response_model=GenerateDailyPlannerResponse)
@limiter.limit("5/minute")
async def generate_daily_planner_for_user(
    user_id: UUID,
    request: Request,
    target_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    recommendation = await generate_daily_recommendation(
        db=db,
        user_id=user_id,
        target_date=target_date,
    )
    return {"recommendation": recommendation}


@router.post("/generate", response_model=GenerateDailyPlannerResponse)
@limiter.limit("5/minute")
async def generate_my_daily_planner(
    request: Request,
    target_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recommendation = await generate_daily_recommendation(
        db=db,
        user_id=current_user.id,
        target_date=target_date,
    )
    return {"recommendation": recommendation}


@router.get("/date/{recommendation_date}", response_model=DailyRecommendationResponse)
async def get_my_daily_recommendation(
    recommendation_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_recommendation_by_date(
        db=db,
        user_id=current_user.id,
        recommendation_date=recommendation_date,
    )


@router.get("/{user_id}/date/{recommendation_date}", response_model=DailyRecommendationResponse)
async def get_daily_recommendation_for_user(
    user_id: UUID,
    recommendation_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await get_recommendation_by_date(
        db=db,
        user_id=user_id,
        recommendation_date=recommendation_date,
    )
