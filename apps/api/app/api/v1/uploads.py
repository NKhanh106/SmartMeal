"""
Image upload API endpoints.

Base path: /api/v1/uploads

Features:
- Upload images (avatar, meal, progress, temporary)
- List user's images (with pagination and type filter)
- Get single image metadata
- Delete image (soft delete + physical file removal)
- Serve uploaded images via /uploads/ static mount
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.uploaded_image import (
    ImageType,
    UploadedImageListResponse,
    UploadedImageResponse,
)
from app.services.image_storage_service import (
    delete_image,
    get_image_metadata,
    list_user_images,
    save_image,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["Image Uploads"])


@router.post("", response_model=UploadedImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(..., description="Image file to upload"),
    image_type: ImageType = Form(..., description="avatar | meal | progress | temporary"),
    linked_entity_type: str | None = Form(default=None),
    linked_entity_id: UUID | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an image and store metadata in DB.

    - **file**: JPEG, PNG, or WebP image (max 5 MB by default)
    - **image_type**:
        - `avatar` — never auto-deleted
        - `meal` — expires after 7 days
        - `temporary` — expires after 1 day
        - `progress` — never auto-deleted
    - **linked_entity_type**: optional entity to link this image to (e.g. "meal_log")
    - **linked_entity_id**: optional ID of the linked entity
    """
    result = await save_image(
        db=db,
        file=file,
        user_id=current_user.id,
        image_type=image_type,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
    )
    logger.info(
        "Image uploaded: id=%s type=%s user=%s",
        result.id,
        image_type,
        current_user.id,
    )
    return result


@router.get("", response_model=UploadedImageListResponse)
async def list_images(
    image_type: ImageType | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all non-deleted images belonging to the authenticated user.

    - **image_type**: filter by type (optional)
    - **skip**: pagination offset (default 0)
    - **limit**: page size (default 20, max 100)
    """
    items, total = await list_user_images(
        db=db,
        user_id=current_user.id,
        image_type=image_type,
        skip=skip,
        limit=limit,
    )
    return UploadedImageListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{image_id}", response_model=UploadedImageResponse)
async def get_image(
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get metadata for a single image.

    Returns 404 if the image doesn't exist, is deleted, or belongs to another user.
    """
    result = await get_image_metadata(db=db, image_id=image_id, user_id=current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found.",
        )
    return result


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_image(
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-delete an image and remove the physical file.

    Only the image owner can delete their own images.
    Returns 204 No Content on success, 404 if image not found.
    """
    deleted = await delete_image(db=db, image_id=image_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found.",
        )
    logger.info("Image deleted: id=%s user=%s", image_id, current_user.id)
