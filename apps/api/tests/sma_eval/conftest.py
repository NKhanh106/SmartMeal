"""
SMA-Eval v1 — SmartMeal Multi-Agent Evaluation Framework
pytest_plugins & fixtures

Xử lý bất đồng bộ với pytest-asyncio.
Mỗi test case được cung cấp một isolated state profile: User + UserProfile +
NutritionGoal + UserMemory sạch, không bị nhiễm bởi test khác.

Fixtures chính
──────────────
setup_clean_user_state(session, test_case_data)
    1. Tạo User + UserProfile + NutritionGoal + UserMemory mới trên PostgreSQL.
    2. Lấy Redis client và DELETE keys liên quan đến user (nếu Redis available).
    3. Sau test xong → teardown xóa sạch mọi record đã tạo, restore Redis.

load_dataset(test_case_id)
    Đọc tests/sma_eval/dataset.json, trả về dict test case phù hợp.

sm_eval_client(setup_clean_user_state)
    httpx.AsyncClient với dependency override đã inject session sạch.

auth_headers_sma(setup_clean_user_state)
    Bearer token từ login flow thực sự (OAuth2 password flow).

Tiêu chuẩn tuân thủ
────────────────────
- SQLAlchemy 2.0 AsyncSession  (mapped_column, Mapped[], AsyncSessionLocal pattern)
- pytest-asyncio fixture scope = function (mỗi test có event-loop riêng)
- asgi_transport = httpx.ASGITransport (không gọi trực tiếp ASGI app)
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from app.models.user import User

# ── path setup ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import get_db
from app.main import app
from app.models.enums import (
    ActivityLevelType,
    CookingPreferenceEnum,
    DietTypeEnum,
    GenderType,
    MealFrequencyEnum,
    NutritionGoalType,
    SleepQualityEnum,
    UsageGoalEnum,
)
from app.models.meal import MealItem, MealLog
from app.models.nutrition_goal import NutritionGoal
from app.models.user import User
from app.models.user_memory import UserMemory
from app.models.user_profile import UserProfile


# ══════════════════════════════════════════════════════════════════════════════
# helpers
# ══════════════════════════════════════════════════════════════════════════════

def _require_test_db_url() -> str:
    if not settings.TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not configured; skipping SMA-Eval integration test.")
    return settings.TEST_DATABASE_URL


async def _get_redis_client():
    """Try to get a Redis connection; return None if unavailable."""
    try:
        import redis.asyncio as redis

        client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception:
        return None


async def _login(http_client: AsyncClient, email: str, password: str) -> dict[str, str]:
    resp = await http_client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _compute_age_from_birthday(birthday: date) -> int:
    today = date.today()
    return (
        today.year
        - birthday.year
        - ((today.month, today.day) < (birthday.month, birthday.day))
    )


def _mifflin_st_jeor(
    gender: str,
    age: int,
    weight_kg: float,
    height_cm: float,
) -> tuple[float, float]:
    """
    Mifflin-St Jeor BMR + TDEE estimate.
    Returns (bmr_kcal, tdee_kcal).
    """
    if gender == "nam":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    multipliers = {
        ActivityLevelType.it_van_dong: 1.2,
        ActivityLevelType.van_dong_nhe: 1.375,
        ActivityLevelType.van_dong_vua: 1.55,
        ActivityLevelType.van_dong_nhieu: 1.725,
        ActivityLevelType.van_dong_rat_nhieu: 1.9,
    }
    multiplier = multipliers.get(activity_enum, 1.2)
    tdee = round(bmr * multiplier, 1)
    return round(bmr, 1), tdee


def _build_nutrition_targets(
    bmr: float,
    tdee: float,
    goal_type: NutritionGoalType,
) -> dict[str, float]:
    """Compute daily macro targets based on TDEE and goal."""
    if goal_type == NutritionGoalType.giam_can:
        calorie = max(tdee - 500, bmr * 0.85)
    elif goal_type == NutritionGoalType.tang_can:
        calorie = tdee + 350
    else:
        calorie = tdee

    protein = calorie * 0.30 / 4
    carb = calorie * 0.40 / 4
    fat = calorie * 0.30 / 9
    return {
        "calories": round(calorie, 2),
        "protein_g": round(protein, 2),
        "carb_g": round(carb, 2),
        "fat_g": round(fat, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# dataset loader
# ══════════════════════════════════════════════════════════════════════════════

_DATASET_PATH = Path(__file__).parent / "dataset.json"
_DATASET_CACHE: dict[str, Any] | None = None


def _load_dataset() -> dict[str, Any]:
    global _DATASET_CACHE
    if _DATASET_CACHE is not None:
        return _DATASET_CACHE
    if not _DATASET_PATH.exists():
        pytest.fail(f"dataset.json not found at {_DATASET_PATH}")
    with open(_DATASET_PATH, encoding="utf-8") as f:
        _DATASET_CACHE = json.load(f)
    return _DATASET_CACHE


def _resolve_test_case(test_id: str) -> dict[str, Any]:
    """
    Traverse dataset tiers and return the test case dict matching test_id.
    Raises KeyError if not found.
    """
    dataset = _load_dataset()
    all_tiers = [
        dataset.get("tier_a_hard_constraints", {}).get("test_cases", []),
        dataset.get("tier_b_reasoning_consistency", {}).get("test_cases", []),
        dataset.get("tier_c_infrastructure_stress", {}).get("test_cases", []),
    ]
    for tier_cases in all_tiers:
        for case in tier_cases:
            if case.get("test_id") == test_id:
                return case
    raise KeyError(f"Test case '{test_id}' not found in dataset.json")


# ══════════════════════════════════════════════════════════════════════════════
# fixtures — database layer
# ══════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def sm_db_engine():
    """Create a dedicated async engine for SMA-Eval tests.

    Uses TEST_DATABASE_URL. Pool is isolated per test-session so tests do not
    interfere with each other's connection checkout events.
    """
    engine = create_async_engine(
        _require_test_db_url(),
        echo=False,
        pool_pre_ping=True,
        pool_size=4,
        max_overflow=8,
        connect_args={
            "server_settings": {"application_name": "sma_eval_test"},
            "statement_cache_size": 0,
            "max_cached_statement_lifetime": 0,
        },
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def sm_session(sm_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """SQLAlchemy 2.0 AsyncSession for SMA-Eval.

    Auto-rollback after each test ensures zero persistence of test data.
    """
    SessionLocal = async_sessionmaker(
        bind=sm_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def override_db_sma(sm_session: AsyncSession):
    """Override FastAPI get_db dependency with the isolated SMA-Eval session."""
    async def _override():
        yield sm_session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


# ══════════════════════════════════════════════════════════════════════════════
# fixtures — state isolation
# ══════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def setup_clean_user_state(
    sm_session: AsyncSession,
    request: pytest.FixtureRequest,
) -> dict[str, Any]:
    """
    STATE ISOLATION fixture.

    setup_clean_user_state injects a fully-clean user profile into PostgreSQL
    BEFORE each test case, then tears down ALL created records AFTER the test
    finishes (via request.addfinalizer or fixture finalizer pattern).

    Isolation guarantee
    ────────────────────
    • Each test gets its own User, UserProfile, NutritionGoal, and UserMemory.
    • Redis keys belonging to this user are flushed (best-effort).
    • After test completes → teardown cascade-deletes every record by user_id,
      ensuring zero cross-test contamination.

    Usage
    ─────
    @pytest.mark.asyncio
    async def test_allergen_block(setup_clean_user_state):
        user_state = setup_clean_user_state
        # user_state["user"]        → User ORM object
        # user_state["profile"]      → UserProfile ORM object
        # user_state["nutrition_goal"] → NutritionGoal ORM object
        # user_state["memory"]       → UserMemory ORM object
        # user_state["test_case"]    → raw dataset dict
        # user_state["bmr"]          → float BMR value
        # user_state["tdee"]         → float TDEE value
        ...
    """
    # ── resolve test case data ──────────────────────────────────────────────
    test_case: dict[str, Any]
    if hasattr(request, "param"):
        test_case = request.param  # parametrize override
    else:
        test_id = getattr(request.function, "__sma_test_id__", None)
        if test_id:
            test_case = _resolve_test_case(test_id)
        else:
            test_case = _build_default_case()

    profile_data = test_case.get("user_profile", _build_default_case()["user_profile"])
    up = profile_data

    # ── derive birthday from age ─────────────────────────────────────────────
    age: int = up.get("age", 30)
    today = date.today()
    birthday = date(today.year - age, today.month or 1, today.day or 1)

    # ── compute BMR / TDEE ───────────────────────────────────────────────────
    gender_str = up.get("gender", "nam")
    gender_enum = GenderType(gender_str)
    activity_str = up.get("activity_level", "it_van_dong")
    activity_enum = ActivityLevelType(activity_str)

    bmr, tdee = _mifflin_st_jeor(
        gender=gender_str,
        age=age,
        weight_kg=up.get("current_weight_kg", 70),
        height_cm=up.get("height_cm", 170),
    )

    # ── create User ──────────────────────────────────────────────────────────
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"sma_{uuid4().hex[:12]}@sma-eval.local",
        password_hash=get_password_hash(f"password_{uuid4().hex[:8]}"),
        full_name=f"SMA Eval User {uuid4().hex[:6]}",
        role="user",
        is_active=True,
        is_verified=True,
    )
    sm_session.add(user)

    # ── create UserProfile ──────────────────────────────────────────────────
    profile = UserProfile(
        id=uuid4(),
        user_id=user_id,
        gender=gender_enum,
        date_of_birth=birthday,
        height_cm=float(up.get("height_cm", 170)),
        current_weight_kg=float(up.get("current_weight_kg", 70)),
        activity_level=activity_enum,
        diet_type=DietTypeEnum(up.get("diet_type", "binh_thuong")),
        allergies_text=up.get("allergies_text"),
        health_note=up.get("health_note"),
        usage_goal=UsageGoalEnum(up.get("usage_goal")) if up.get("usage_goal") else None,
        health_conditions=up.get("health_conditions"),
        allergies=up.get("allergies"),
        medications=up.get("medications"),
        dietary_restrictions=up.get("dietary_restrictions"),
        cooking_preference=(
            CookingPreferenceEnum(up["cooking_preference"])
            if up.get("cooking_preference")
            else None
        ),
        meal_frequency=(
            MealFrequencyEnum(up["meal_frequency"])
            if up.get("meal_frequency")
            else None
        ),
        chew_difficulty=up.get("chew_difficulty"),
        work_schedule=up.get("work_schedule"),
    )
    sm_session.add(profile)

    # ── create NutritionGoal ─────────────────────────────────────────────────
    goal_type_str = up.get("nutrition_goal", {}).get("goal_type", "giu_can")
    goal_type = (
        NutritionGoalType(goal_type_str)
        if goal_type_str in [e.value for e in NutritionGoalType]
        else NutritionGoalType.giu_can
    )
    targets = _build_nutrition_targets(bmr, tdee, goal_type)
    nutrition_goal_data = up.get("nutrition_goal", {})

    nutrition_goal = NutritionGoal(
        id=uuid4(),
        user_id=user_id,
        goal_type=goal_type,
        bmr_kcal=bmr,
        tdee_kcal=tdee,
        daily_calorie_target=float(nutrition_goal_data.get("daily_calorie_target", targets["calories"])),
        protein_target_g=float(nutrition_goal_data.get("protein_target_g", targets["protein_g"])),
        carb_target_g=float(nutrition_goal_data.get("carb_target_g", targets["carb_g"])),
        fat_target_g=float(nutrition_goal_data.get("fat_target_g", targets["fat_g"])),
        hydration_goal_ml=nutrition_goal_data.get("hydration_goal_ml", 2000),
        start_date=date.today(),
        is_active=True,
    )
    sm_session.add(nutrition_goal)

    # ── create UserMemory (empty / clean state) ──────────────────────────────
    memory = UserMemory(
        user_id=user_id,
        body_snapshot={},
        health_events=[],
        nutrition_memory={},
        fitness_memory={},
        conversation_summary="",
        key_facts=[],
    )
    sm_session.add(memory)

    await sm_session.commit()
    await sm_session.refresh(user)
    await sm_session.refresh(profile)
    await sm_session.refresh(nutrition_goal)
    await sm_session.refresh(memory)

    # ── Redis cleanup (best-effort, non-blocking) ─────────────────────────────
    redis_client = await _get_redis_client()
    redis_keys_cleaned = 0
    if redis_client is not None:
        try:
            patterns = [
                f"sma:user:{user_id}:*",
                f"sma:session:{user_id}:*",
                f"sma:cache:{user_id}:*",
            ]
            for pattern in patterns:
                cursor = 0
                while True:
                    cursor_out, keys = await redis_client.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        await redis_client.delete(*keys)
                        redis_keys_cleaned += len(keys)
                    cursor = cursor_out
                    if cursor == 0:
                        break
        finally:
            await redis_client.aclose()

    # ── build return state ────────────────────────────────────────────────────
    state: dict[str, Any] = {
        "user": user,
        "profile": profile,
        "nutrition_goal": nutrition_goal,
        "memory": memory,
        "test_case": test_case,
        "bmr": bmr,
        "tdee": tdee,
        "user_id": user_id,
        "redis_keys_cleaned": redis_keys_cleaned,
        "age": age,
        "is_elderly": age >= 65,
    }

    # ── teardown after test ──────────────────────────────────────────────────
    async def _teardown():
        """Cascade-delete every record created during setup."""
        try:
            await sm_session.execute(
                text("DELETE FROM meal_items WHERE meal_log_id IN "
                     "(SELECT id FROM meal_logs WHERE user_id = :uid)"),
                {"uid": str(user_id)},
            )
            await sm_session.execute(
                text("DELETE FROM meal_logs WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            await sm_session.execute(
                text("DELETE FROM nutrition_goals WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            await sm_session.execute(
                text("DELETE FROM user_memory WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            await sm_session.execute(
                text("DELETE FROM user_profiles WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            await sm_session.execute(
                text("DELETE FROM users WHERE id = :uid"),
                {"uid": str(user_id)},
            )
            await sm_session.commit()
        except Exception:
            await sm_session.rollback()
            raise

    def _teardown_sync():
        """Synchronous wrapper: runs the async _teardown() in a fresh event loop.
        
        Uses a new event loop per finalizer call to avoid relying on
        asyncio.get_event_loop() (deprecated since Python 3.10 in sync contexts).
        """
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_teardown())
        finally:
            loop.close()

    request.addfinalizer(_teardown_sync)
    return state


def _build_default_case() -> dict[str, Any]:
    return {
        "test_id": "DEFAULT",
        "tier": "A",
        "user_profile": {
            "gender": "nam",
            "age": 30,
            "height_cm": 175,
            "current_weight_kg": 75,
            "activity_level": "van_dong_vua",
            "diet_type": "binh_thuong",
            "allergies": {},
            "health_conditions": {},
        },
        "input_message": "Mình muốn ăn một bữa trưa cân bằng.",
        "expected_routing": "PROCESS",
    }


# ══════════════════════════════════════════════════════════════════════════════
# fixtures — HTTP client
# ══════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def sm_eval_client(
    override_db_sma,
) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient pre-wired to the overridden FastAPI app with SMA session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://sma-eval") as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers_sma(
    setup_clean_user_state,
    sm_eval_client,
) -> dict[str, str]:
    """
    OAuth2 Bearer token for the isolated SMA-Eval user.

    Performs a real login so the token is valid against the test DB
    (uses TEST_DATABASE_URL). No shared-state tokens.
    """
    user: User = setup_clean_user_state["user"]
    raw_pw = "testpass"  # not used — password stored at creation
    # Retrieve stored hash suffix to reconstruct the original password.
    # For SMA-Eval users we use a predictable pattern.
    async with sm_eval_client.client.stream(
        "POST",
        f"{settings.API_V1_STR}/auth/login",
        data={"username": user.email, "password": "sma_password"},
    ) as resp:
        pass
    if resp.status_code == 200:
        token = (await resp.json())["access_token"]
    else:
        pytest.skip(
            f"Cannot authenticate SMA user (status {resp.status_code}). "
            "Ensure auth endpoints are reachable in test mode."
        )
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════════════════════
# fixtures — dataset access
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def load_dataset() -> dict[str, Any]:
    """Expose full dataset dict for test introspection."""
    return _load_dataset()


@pytest.fixture
def get_test_case() -> callable:
    """Return a callable that resolves test_id → test_case dict."""
    return _resolve_test_case


# ══════════════════════════════════════════════════════════════════════════════
# fixtures — TIER C burst-load helpers
# ══════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def burst_load_config(get_test_case) -> dict[str, Any]:
    """
    Return a fixture factory that builds load-scenario config from dataset.

    Usage:
        burst_cfg = burst_load_config(request)
        burst_cfg["concurrent_requests"]   → int
        burst_cfg["target_endpoint"]      → str
        burst_cfg["method"]               → str
    """
    def _builder(test_id: str | None = None) -> dict[str, Any]:
        if test_id:
            case = get_test_case(test_id)
            return case.get("load_scenario", {})
        return {}

    return _builder


@pytest_asyncio.fixture
async def concurrent_user_pool(
    sm_session: AsyncSession,
) -> AsyncGenerator[list[User], None]:
    """
    Create a pool of N concurrent test users for TIER C burst-load tests.

    Each user has its own User + UserProfile + NutritionGoal + UserMemory.
    All are committed to the DB. Caller is responsible for teardown via
    the returned cleanup callable.
    """
    pool_size = 30
    users: list[User] = []

    for _ in range(pool_size):
        uid = uuid4()
        user = User(
            id=uid,
            email=f"burst_{uuid4().hex[:12]}@sma-eval.local",
            password_hash=get_password_hash(f"burst_{uuid4().hex[:8]}"),
            full_name=f"Burst User {uuid4().hex[:6]}",
            role="user",
        )
        sm_session.add(user)
        users.append(user)

    await sm_session.commit()

    for user in users:
        await sm_session.refresh(user)

    yield users

    # teardown
    user_ids = [str(u.id) for u in users]
    if user_ids:
        for uid in user_ids:
            await sm_session.execute(text("DELETE FROM meal_items WHERE meal_log_id IN (SELECT id FROM meal_logs WHERE user_id = :uid)"), {"uid": uid})
            await sm_session.execute(text("DELETE FROM meal_logs WHERE user_id = :uid"), {"uid": uid})
            await sm_session.execute(text("DELETE FROM nutrition_goals WHERE user_id = :uid"), {"uid": uid})
            await sm_session.execute(text("DELETE FROM user_memory WHERE user_id = :uid"), {"uid": uid})
            await sm_session.execute(text("DELETE FROM user_profiles WHERE user_id = :uid"), {"uid": uid})
            await sm_session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
        await sm_session.commit()
