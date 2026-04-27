import sys
from pathlib import Path
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import get_db
from app.main import app
from app.models.user import User


def _require_test_database_url() -> str:
    if not settings.TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not configured; skipping DB integration test.")
    return settings.TEST_DATABASE_URL


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    test_engine = create_async_engine(
        _require_test_database_url(),
        echo=False,
        pool_pre_ping=True,
    )
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    await test_engine.dispose()


@pytest_asyncio.fixture
async def override_db(db_session: AsyncSession):
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(override_db) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"test_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("testpass123"),
        full_name="Test User",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession) -> User:
    admin = User(
        email=f"admin_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("adminpass123"),
        full_name="Admin User",
        role="admin",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(test_user: User, client: AsyncClient) -> dict:
    return await _login(client, test_user.email, "testpass123")


@pytest_asyncio.fixture
async def admin_headers(test_admin: User, client: AsyncClient) -> dict:
    return await _login(client, test_admin.email, "adminpass123")
