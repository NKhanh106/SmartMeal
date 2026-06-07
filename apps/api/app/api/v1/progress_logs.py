from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.progress_log import (
    ProgressLogCreate,
    ProgressLogResponse,
    ProgressLogUpdate,
)
from app.services.progress_log_service import (
    create_or_update_progress_log,
    delete_progress_log,
    get_latest_progress_log,
    get_progress_log_by_id,
    get_user_progress_logs,
    update_progress_log,
)
from app.services.daily_recommendation_service import invalidate_user_plan_cache

router = APIRouter(prefix="/progress-logs", tags=["Progress Logs"])


@router.post("/", response_model=ProgressLogResponse, status_code=201)
async def create_progress_log(
    payload: ProgressLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await create_or_update_progress_log(
        db=db,
        user_id=current_user.id,
        log_date=payload.log_date,
        weight_kg=payload.weight_kg,
        body_fat_percent=payload.body_fat_percent,
        waist_cm=payload.waist_cm,
        neck_cm=payload.neck_cm,
        chest_cm=payload.chest_cm,
        hip_cm=payload.hip_cm,
        progress_photo_url=payload.progress_photo_url,
        note=payload.note,
    )
    await db.commit()
    await invalidate_user_plan_cache(current_user.id)
    await db.refresh(record)
    return record


@router.get("/user", response_model=list[ProgressLogResponse])
async def get_my_progress_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    return await get_user_progress_logs(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get("/user/{user_id}", response_model=list[ProgressLogResponse])
async def get_user_progress_logs_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await get_user_progress_logs(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/user/{user_id}/latest", response_model=ProgressLogResponse)
async def get_user_latest_progress_log(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    record = await get_latest_progress_log(db=db, user_id=user_id)
    if record is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No progress log found for this user.")
    return record


@router.get("/{progress_log_id}", response_model=ProgressLogResponse)
async def get_progress_log_detail(
    progress_log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await get_progress_log_by_id(db=db, progress_log_id=progress_log_id)
    ensure_user_access(current_user, record.user_id)
    return record


@router.put("/{progress_log_id}", response_model=ProgressLogResponse)
async def update_my_progress_log(
    progress_log_id: UUID,
    payload: ProgressLogUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await update_progress_log(
        db=db,
        progress_log_id=progress_log_id,
        user_id=current_user.id,
        **payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    await invalidate_user_plan_cache(current_user.id)
    await db.refresh(record)
    return record


@router.delete("/{progress_log_id}", status_code=204)
async def delete_my_progress_log(
    progress_log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await delete_progress_log(
        db=db,
        progress_log_id=progress_log_id,
        user_id=current_user.id,
    )
    await db.commit()
    await invalidate_user_plan_cache(current_user.id)
    return None
