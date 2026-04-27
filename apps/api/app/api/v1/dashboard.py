from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DailyDashboardResponse, WeeklyDashboardResponse
from app.services.dashboard_service import get_daily_dashboard, get_weekly_dashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/today", response_model=DailyDashboardResponse)
async def get_my_daily_dashboard(
    target_date: date = Query(default_factory=date.today),
    timezone_str: str = Query(default="Asia/Ho_Chi_Minh"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_daily_dashboard(
        db=db,
        user_id=current_user.id,
        target_date=target_date,
        timezone_str=timezone_str,
    )


@router.get("/weekly", response_model=WeeklyDashboardResponse)
async def get_my_weekly_dashboard(
    end_date: date = Query(default_factory=date.today),
    timezone_str: str = Query(default="Asia/Ho_Chi_Minh"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_weekly_dashboard(
        db=db,
        user_id=current_user.id,
        end_date=end_date,
        timezone_str=timezone_str,
    )


@router.get("/user/{user_id}/today", response_model=DailyDashboardResponse)
async def get_user_daily_dashboard(
    user_id: UUID,
    target_date: date = Query(default_factory=date.today),
    timezone_str: str = Query(default="Asia/Ho_Chi_Minh"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await get_daily_dashboard(
        db=db,
        user_id=user_id,
        target_date=target_date,
        timezone_str=timezone_str,
    )


@router.get("/user/{user_id}/weekly", response_model=WeeklyDashboardResponse)
async def get_user_weekly_dashboard(
    user_id: UUID,
    end_date: date = Query(default_factory=date.today),
    timezone_str: str = Query(default="Asia/Ho_Chi_Minh"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await get_weekly_dashboard(
        db=db,
        user_id=user_id,
        end_date=end_date,
        timezone_str=timezone_str,
    )
