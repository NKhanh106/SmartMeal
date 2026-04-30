from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progress_log import ProgressLog


async def create_or_update_progress_log(
    db: AsyncSession,
    user_id: UUID,
    log_date: date,
    weight_kg=None,
    body_fat_percent=None,
    waist_cm=None,
    neck_cm=None,
    chest_cm=None,
    hip_cm=None,
    progress_photo_url=None,
    note=None,
) -> ProgressLog:
    existing = await db.execute(
        select(ProgressLog).where(
            and_(
                ProgressLog.user_id == user_id,
                ProgressLog.log_date == log_date,
            )
        )
    )
    record = existing.scalar_one_or_none()

    if record is not None:
        if weight_kg is not None:
            record.weight_kg = weight_kg
        if body_fat_percent is not None:
            record.body_fat_percent = body_fat_percent
        if waist_cm is not None:
            record.waist_cm = waist_cm
        if neck_cm is not None:
            record.neck_cm = neck_cm
        if chest_cm is not None:
            record.chest_cm = chest_cm
        if hip_cm is not None:
            record.hip_cm = hip_cm
        # Cho phép clear bằng sentinel value rõ ràng
        if progress_photo_url is not None:
            record.progress_photo_url = progress_photo_url
        if note is not None:
            record.note = note
    else:
        record = ProgressLog(
            user_id=user_id,
            log_date=log_date,
            weight_kg=weight_kg,
            body_fat_percent=body_fat_percent,
            waist_cm=waist_cm,
            neck_cm=neck_cm,
            chest_cm=chest_cm,
            hip_cm=hip_cm,
            progress_photo_url=progress_photo_url,
            note=note,
        )
        db.add(record)

    await db.flush()
    return record


async def get_user_progress_logs(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[ProgressLog]:
    result = await db.execute(
        select(ProgressLog)
        .where(ProgressLog.user_id == user_id)
        .order_by(ProgressLog.log_date.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_progress_log(
    db: AsyncSession,
    user_id: UUID,
) -> ProgressLog | None:
    result = await db.execute(
        select(ProgressLog)
        .where(ProgressLog.user_id == user_id)
        .order_by(ProgressLog.log_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_progress_log_by_id(
    db: AsyncSession,
    progress_log_id: UUID,
) -> ProgressLog:
    result = await db.execute(
        select(ProgressLog).where(ProgressLog.id == progress_log_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress log not found.",
        )
    return record


async def update_progress_log(
    db: AsyncSession,
    progress_log_id: UUID,
    user_id: UUID,
    weight_kg=None,
    body_fat_percent=None,
    waist_cm=None,
    neck_cm=None,
    chest_cm=None,
    hip_cm=None,
    progress_photo_url=None,
    note=None,
) -> ProgressLog:
    record = await get_progress_log_by_id(db, progress_log_id)
    if record.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this progress log.",
        )

    if weight_kg is not None:
        record.weight_kg = weight_kg
    if body_fat_percent is not None:
        record.body_fat_percent = body_fat_percent
    if waist_cm is not None:
        record.waist_cm = waist_cm
    if neck_cm is not None:
        record.neck_cm = neck_cm
    if chest_cm is not None:
        record.chest_cm = chest_cm
    if hip_cm is not None:
        record.hip_cm = hip_cm
    if progress_photo_url is not None:
        record.progress_photo_url = progress_photo_url
    if note is not None:
        record.note = note

    await db.flush()
    return record


async def delete_progress_log(
    db: AsyncSession,
    progress_log_id: UUID,
    user_id: UUID,
) -> None:
    record = await get_progress_log_by_id(db, progress_log_id)
    if record.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this progress log.",
        )
    await db.delete(record)
    await db.flush()
