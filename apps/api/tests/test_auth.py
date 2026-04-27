"""Tests cho Auth flow: Register, Login, /me, Error cases."""
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import settings

API = settings.API_V1_STR


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Register trả 201 và user info."""
    email = f"new_{uuid4().hex[:8]}@example.com"
    resp = await client.post(f"{API}/auth/register", json={
        "email": email,
        "password": "securePass123",
        "full_name": "New User",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == email
    assert data["full_name"] == "New User"
    assert data["role"] == "user"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user):
    """Register với email đã tồn tại trả 409."""
    resp = await client.post(f"{API}/auth/register", json={
        "email": test_user.email,
        "password": "anyPassword123",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    """Login đúng credentials trả token."""
    resp = await client.post(f"{API}/auth/login", data={
        "username": test_user.email,
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    """Login sai password trả 401."""
    resp = await client.post(f"{API}/auth/login", data={
        "username": test_user.email,
        "password": "wrongPassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers: dict, test_user):
    """GET /auth/me trả user info từ token."""
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == test_user.email


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    """GET /auth/me không có token trả 401."""
    resp = await client.get(f"{API}/auth/me")
    assert resp.status_code == 401
