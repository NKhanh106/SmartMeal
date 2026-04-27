"""Tests cho User Profile CRUD endpoints."""
import pytest
from httpx import AsyncClient

from app.core.config import settings

API = settings.API_V1_STR


@pytest.mark.asyncio
async def test_create_profile(client: AsyncClient, auth_headers: dict):
    """Tạo profile trả 201."""
    resp = await client.post(f"{API}/user-profiles/", json={
        "gender": "nam",
        "date_of_birth": "1998-06-10",
        "height_cm": 175,
        "current_weight_kg": 70,
        "activity_level": "van_dong_vua",
        "diet_type": "binh_thuong",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["height_cm"] == 175
    assert data["current_weight_kg"] == 70


@pytest.mark.asyncio
async def test_get_profile_me(client: AsyncClient, auth_headers: dict):
    """GET /profiles/me yêu cầu auth."""
    resp = await client.get(f"{API}/user-profiles/me", headers=auth_headers)
    # Có thể 200 (nếu profile tồn tại) hoặc 404 (nếu chưa tạo)
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_profile_unauthorized(client: AsyncClient):
    """Truy cập profile không có token trả 401."""
    resp = await client.get(f"{API}/user-profiles/me")
    assert resp.status_code == 401
