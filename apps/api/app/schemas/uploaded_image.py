from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ImageType = Literal["avatar", "meal", "progress", "temporary"]


class UploadedImageResponse(BaseModel):
    """Response returned after a successful image upload."""

    id: UUID
    image_type: ImageType
    url: str = Field(description="Public URL to access the image")
    content_type: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class UploadedImageListItem(BaseModel):
    """Lightweight response for image listings."""

    id: UUID
    image_type: ImageType
    url: str
    content_type: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UploadedImageListResponse(BaseModel):
    items: list[UploadedImageListItem]
    total: int
    skip: int
    limit: int


class ImageCleanupResult(BaseModel):
    """Result from a cleanup run."""

    deleted_count: int = 0
    errors: list[str] = Field(default_factory=list)
