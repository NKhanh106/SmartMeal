import hashlib
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.uploaded_image import ImageTypeEnum, UploadedImage
from app.schemas.uploaded_image import (
    ImageCleanupResult,
    UploadedImageResponse,
)

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
_WEBP_RIFF = b"RIFF"
_WEBP_WEBP = b"WEBP"

_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Safe characters for filenames (no path traversal)
_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_.-]")


def _sanitize_original_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    safe_name = _SAFE_FILENAME_RE.sub("_", name).strip("._")
    if not safe_name:
        safe_name = "upload"
    safe_ext = _SAFE_FILENAME_RE.sub("", ext).lower()
    return f"{safe_name}{safe_ext}"


def _get_retention_days(image_type: str) -> int | None:
    """Return TTL in days for a given image_type, or None for no auto-delete."""
    if image_type == ImageTypeEnum.AVATAR:
        return None
    if image_type == ImageTypeEnum.MEAL:
        return settings.IMAGE_RETENTION_DAYS_MEAL
    if image_type == ImageTypeEnum.TEMPORARY:
        return settings.IMAGE_RETENTION_DAYS_TEMPORARY
    if image_type == ImageTypeEnum.PROGRESS:
        return settings.IMAGE_RETENTION_DAYS_PROGRESS
    return None


def _compute_expires_at(image_type: str, created_at: datetime) -> datetime | None:
    days = _get_retention_days(image_type)
    if days is None:
        return None
    return created_at + timedelta(days=days)


def _build_storage_dir(upload_dir: Path, user_id: UUID, image_type: str) -> Path:
    return upload_dir / str(user_id) / image_type


async def validate_image_upload(file: UploadFile) -> bytes:
    """
    Validate uploaded file:
    - Allowed MIME types only
    - Size within MAX_IMAGE_SIZE_BYTES
    - Magic bytes match declared content type

    Returns raw bytes on success.
    Raises HTTPException on validation failure.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image/jpeg, image/png, image/webp are allowed.",
        )

    bytes_read = await file.read()
    file_size = len(bytes_read)

    if file_size > settings.MAX_IMAGE_SIZE_BYTES:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image file too large. Maximum size is {settings.MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    if file_size == 0:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file is not allowed.",
        )

    # Magic bytes validation
    is_valid = False
    if file.content_type == "image/jpeg":
        is_valid = bytes_read.startswith(_JPEG_MAGIC)
    elif file.content_type == "image/png":
        is_valid = bytes_read.startswith(_PNG_MAGIC)
    elif file.content_type == "image/webp":
        is_valid = (
            bytes_read.startswith(_WEBP_RIFF)
            and len(bytes_read) >= 12
            and bytes_read[8:12] == _WEBP_WEBP
        )

    if not is_valid:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match its declared MIME type.",
        )

    # Reset cursor for downstream reads
    await file.seek(0)
    return bytes_read


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def save_image(
    db: AsyncSession,
    file: UploadFile,
    user_id: UUID,
    image_type: str,
    linked_entity_type: str | None = None,
    linked_entity_id: UUID | None = None,
) -> UploadedImageResponse:
    """
    Validate, persist image to disk, insert DB record, return response.

    Atomicity: if DB insert fails after file is written, the file is removed.
    """
    image_bytes = await validate_image_upload(file)

    image_id = uuid4()
    content_type = file.content_type or "application/octet-stream"
    ext = _CONTENT_TYPE_TO_EXT.get(content_type, ".bin")
    stored_filename = f"{image_id}{ext}"

    upload_dir = Path(settings.UPLOAD_DIR)
    storage_path = _build_storage_dir(upload_dir, user_id, image_type)

    # Create directory
    storage_path.mkdir(parents=True, exist_ok=True)

    full_path = storage_path / stored_filename
    relative_key = str(full_path.relative_to(upload_dir))

    # Write file
    try:
        with open(full_path, "wb") as f:
            f.write(image_bytes)
    except OSError as exc:
        logger.error("Failed to write image file %s: %s", full_path, exc)
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save image file.",
        )

    now = datetime.utcnow()
    expires_at = _compute_expires_at(image_type, now)
    checksum = _compute_checksum(image_bytes)

    record = UploadedImage(
        id=image_id,
        user_id=user_id,
        image_type=image_type,
        original_filename=_sanitize_original_filename(file.filename or "unknown"),
        stored_filename=stored_filename,
        storage_key=relative_key,
        content_type=content_type,
        file_size=len(image_bytes),
        checksum=checksum,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
    )

    try:
        db.add(record)
        await db.commit()
        await db.refresh(record)
    except Exception as exc:
        # Rollback DB; remove orphan file
        logger.warning("DB insert failed for image %s, removing orphan file: %s", image_id, exc)
        try:
            os.remove(full_path)
        except OSError:
            pass
        await db.rollback()
        raise

    url = f"{settings.IMAGE_PUBLIC_BASE_URL}/{relative_key.replace(os.sep, '/')}"

    return UploadedImageResponse.model_validate(record, update={"url": url})


async def get_image_metadata(
    db: AsyncSession,
    image_id: UUID,
    user_id: UUID,
) -> UploadedImageResponse | None:
    """Get image metadata if it belongs to the user and is not deleted."""
    result = await db.execute(
        select(UploadedImage).where(
            UploadedImage.id == image_id,
            UploadedImage.user_id == user_id,
            UploadedImage.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    url = f"{settings.IMAGE_PUBLIC_BASE_URL}/{record.storage_key.replace(os.sep, '/')}"
    return UploadedImageResponse.model_validate(record, update={"url": url})


async def list_user_images(
    db: AsyncSession,
    user_id: UUID,
    image_type: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[UploadedImageResponse], int]:
    """
    List non-deleted images for a user.
    Returns (items, total_count).
    """
    query = select(UploadedImage).where(
        UploadedImage.user_id == user_id,
        UploadedImage.deleted_at.is_(None),
    )
    count_query = select(UploadedImage.id).where(
        UploadedImage.user_id == user_id,
        UploadedImage.deleted_at.is_(None),
    )

    if image_type:
        query = query.where(UploadedImage.image_type == image_type)
        count_query = count_query.where(UploadedImage.image_type == image_type)

    # Total count
    count_result = await db.execute(count_query)
    total = len(count_result.all())

    # Paginated results
    query = query.order_by(UploadedImage.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()

    items = []
    for record in records:
        url = f"{settings.IMAGE_PUBLIC_BASE_URL}/{record.storage_key.replace(os.sep, '/')}"
        items.append(UploadedImageResponse.model_validate(record, update={"url": url}))

    return items, total


async def delete_image(
    db: AsyncSession,
    image_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Soft-delete an image (set deleted_at).
    Only the owner can delete.
    Also removes the physical file.

    Returns True if deleted, False if not found.
    """
    result = await db.execute(
        select(UploadedImage).where(
            UploadedImage.id == image_id,
            UploadedImage.user_id == user_id,
            UploadedImage.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return False

    # Remove physical file
    full_path = Path(settings.UPLOAD_DIR) / record.storage_key
    if full_path.exists():
        try:
            os.remove(full_path)
        except OSError as exc:
            logger.warning("Failed to remove image file %s: %s", full_path, exc)

    record.deleted_at = datetime.utcnow()
    await db.commit()
    return True


async def cleanup_expired_images(db: AsyncSession) -> ImageCleanupResult:
    """
    Soft-delete all expired images (expires_at IS NOT NULL AND expires_at < now).
    Removes physical files before marking deleted.

    Should be run as a scheduled job (daily).
    """
    result = await ImageCleanupResult()

    async with db.begin_nested():
        expired_query = select(UploadedImage).where(
            UploadedImage.expires_at.isnot(None),
            UploadedImage.expires_at < datetime.utcnow(),
            UploadedImage.deleted_at.is_(None),
        )
        query_result = await db.execute(expired_query)
        expired_records = query_result.scalars().all()

    if not expired_records:
        logger.info("No expired images to clean up.")
        return result

    for record in expired_records:
        full_path = Path(settings.UPLOAD_DIR) / record.storage_key
        if full_path.exists():
            try:
                os.remove(full_path)
            except OSError as exc:
                logger.warning(
                    "Failed to remove expired image file %s [%s]: %s",
                    record.id,
                    full_path,
                    exc,
                )
                result.errors.append(f"Failed to remove file for image {record.id}: {exc}")
                continue

        record.deleted_at = datetime.utcnow()
        result.deleted_count += 1

    await db.commit()
    logger.info(
        "Image cleanup completed: %d expired images soft-deleted, %d errors.",
        result.deleted_count,
        len(result.errors),
    )
    return result


async def link_image_to_entity(
    db: AsyncSession,
    image_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> bool:
    """
    Update linked_entity_type and linked_entity_id of an uploaded image.

    If the image is temporary (1-day TTL) and the entity is a meal_log,
    this function also promotes it to a meal image with the correct TTL.

    Returns True if updated, False if image not found.
    """
    from datetime import timedelta as td

    result = await db.execute(
        select(UploadedImage).where(
            UploadedImage.id == image_id,
            UploadedImage.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return False

    record.linked_entity_type = entity_type
    record.linked_entity_id = entity_id
    record.updated_at = datetime.utcnow()

    # Promote temporary preview image to meal image with correct TTL
    if record.image_type == ImageTypeEnum.TEMPORARY and entity_type == "meal_log":
        record.image_type = ImageTypeEnum.MEAL
        days = settings.IMAGE_RETENTION_DAYS_MEAL
        if days is not None:
            record.expires_at = record.created_at + td(days=days)

    await db.commit()
    return True
