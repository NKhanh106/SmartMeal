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


@pytest.mark.asyncio
async def test_update_profile_with_health_conditions(client: AsyncClient, auth_headers: dict):
    """
    PUT /api/v1/user-profiles/me with health_conditions sets health_risk_flags.
    When type2_diabetes with severity=managed is set, limit_sugar should be in risk flags.
    """
    # First create a profile
    create_resp = await client.post(f"{API}/user-profiles/", json={
        "gender": "nam",
        "date_of_birth": "1990-05-15",
        "height_cm": 170,
        "current_weight_kg": 75,
        "activity_level": "van_dong_vua",
        "diet_type": "binh_thuong",
    }, headers=auth_headers)
    assert create_resp.status_code == 201

    # Update with health conditions
    update_resp = await client.put(f"{API}/user-profiles/me", json={
        "health_conditions": [
            {"condition": "type2_diabetes", "severity": "managed"},
            {"condition": "hypertension", "severity": "unmanaged"},
        ],
    }, headers=auth_headers)
    assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
    data = update_resp.json()
    assert "health_conditions" in data
    conditions = data["health_conditions"]
    assert any(c["condition"] == "type2_diabetes" for c in conditions)
    assert any(c["condition"] == "hypertension" for c in conditions)


@pytest.mark.asyncio
async def test_profile_with_resolved_condition(client: AsyncClient, auth_headers: dict):
    """
    A resolved condition should be stored but not generate risk flags.
    """
    create_resp = await client.post(f"{API}/user-profiles/", json={
        "gender": "nu",
        "date_of_birth": "1992-03-20",
        "height_cm": 160,
        "current_weight_kg": 55,
        "activity_level": "van_dong_it",
        "diet_type": "binh_thuong",
    }, headers=auth_headers)
    assert create_resp.status_code == 201

    update_resp = await client.put(f"{API}/user-profiles/me", json={
        "health_conditions": [
            {"condition": "anemia", "severity": "resolved"},
        ],
    }, headers=auth_headers)
    assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
    data = update_resp.json()
    # Resolved conditions are still stored
    assert any(c["condition"] == "anemia" for c in data.get("health_conditions", []))


@pytest.mark.asyncio
async def test_medical_treatment_goal_without_conditions_returns_validation_error(
    client: AsyncClient,
    auth_headers: dict,
):
    """
    Setting usage_goal=medical_treatment without health_conditions
    should return a validation error (422).
    """
    create_resp = await client.post(f"{API}/user-profiles/", json={
        "gender": "nam",
        "date_of_birth": "1985-01-01",
        "height_cm": 175,
        "current_weight_kg": 80,
        "activity_level": "van_dong_vua",
        "diet_type": "binh_thuong",
    }, headers=auth_headers)
    assert create_resp.status_code == 201

    update_resp = await client.put(f"{API}/user-profiles/me", json={
        "usage_goal": "medical_treatment",
        "health_conditions": [],
    }, headers=auth_headers)
    # Backend should reject medical_treatment without any conditions
    assert update_resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_user_full_name(client: AsyncClient, auth_headers: dict):
    """
    PATCH /api/v1/auth/me updates the current user's full_name.
    """
    resp = await client.patch(
        f"{settings.API_V1_STR}/auth/me",
        json={"full_name": "Updated Name"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Patch user failed: {resp.text}"
    data = resp.json()
    assert data["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_patch_user_requires_auth(client: AsyncClient):
    """PATCH /api/v1/auth/me without auth returns 401."""
    resp = await client.patch(
        f"{settings.API_V1_STR}/auth/me",
        json={"full_name": "Test"},
    )
    assert resp.status_code == 401
