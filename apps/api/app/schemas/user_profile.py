# Re-exports from the authoritative schemas/profile.py
from app.schemas.profile import (
    UserProfileCreate,
    UserProfileUpdate,
    UserProfileResponse,
)

__all__ = ["UserProfileCreate", "UserProfileUpdate", "UserProfileResponse"]
