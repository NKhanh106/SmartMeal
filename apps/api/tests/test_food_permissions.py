from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User

API = settings.API_V1_STR


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(
        f"{API}/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_user_created_food_is_forced_to_manual_source(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.post(
        f"{API}/food-nutrition/",
        headers=auth_headers,
        json={
            "food_name": f"User Food {uuid4().hex[:8]}",
            "serving_size_g": 100,
            "calories_per_100g": 120,
            "protein_per_100g": 10,
            "carb_per_100g": 12,
            "fat_per_100g": 4,
            "source": "he_thong",
            "is_verified": True,
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["source"] == "thu_cong"
    assert data["is_verified"] is False


@pytest.mark.asyncio
async def test_user_cannot_update_another_users_food(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
):
    other_user = User(
        email=f"other_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("otherpass123"),
        full_name="Other User",
        role="user",
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    other_headers = await _login(client, other_user.email, "otherpass123")

    created = await client.post(
        f"{API}/food-nutrition/",
        headers=other_headers,
        json={
            "food_name": f"Private Food {uuid4().hex[:8]}",
            "serving_size_g": 100,
            "calories_per_100g": 100,
            "protein_per_100g": 8,
            "carb_per_100g": 10,
            "fat_per_100g": 3,
        },
    )
    assert created.status_code == 201, created.text

    food_id = created.json()["id"]
    response = await client.put(
        f"{API}/food-nutrition/{food_id}",
        headers=auth_headers,
        json={"food_name": "Hacked Name"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_mark_food_verified(
    client: AsyncClient,
    admin_headers: dict,
):
    created = await client.post(
        f"{API}/food-nutrition/",
        headers=admin_headers,
        json={
            "food_name": f"System Food {uuid4().hex[:8]}",
            "serving_size_g": 100,
            "calories_per_100g": 90,
            "protein_per_100g": 4,
            "carb_per_100g": 12,
            "fat_per_100g": 2,
            "source": "he_thong",
            "is_verified": True,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["is_verified"] is True
