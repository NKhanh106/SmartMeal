"""
Hard-coded rules that fire BEFORE the AI processes a message.
If a rule matches, a card is returned immediately without calling the AI.
The AI will be called again after the user answers the card.
"""

from app.models import UserProfile
from app.schemas.chat_card import ChatCard, CardType, CardOption
import uuid


def check_hard_rule_triggers(
    user_message: str,
    profile: UserProfile | None,
    fired_triggers: list[str] | None,
) -> tuple[ChatCard | None, str | None]:
    """
    Returns (ChatCard, trigger_reason) if a hard rule fires, else (None, None).
    Hard rules take priority over AI-driven cards.
    A trigger only fires once per session — tracked via fired_triggers.
    """
    fired = fired_triggers or []

    # Rule 1: No profile at all
    if profile is None and "missing_profile" not in fired:
        card = ChatCard(
            card_id=str(uuid.uuid4()),
            card_type=CardType.CONFIRM,
            title="Bạn chưa có hồ sơ dinh dưỡng",
            subtitle="Mình cần một vài thông tin cơ bản để tư vấn chính xác hơn. Tạo hồ sơ ngay không?",
            options=None,
            trigger_reason="missing_profile",
            skippable=True,
        )
        return card, "missing_profile"

    # Rule 2: No usage_goal set + nutrition question
    if (
        profile is not None
        and profile.usage_goal is None
        and "missing_goal" not in fired
        and _is_nutrition_question(user_message)
    ):
        card = ChatCard(
            card_id=str(uuid.uuid4()),
            card_type=CardType.SINGLE_SELECT,
            title="Mục tiêu chính của bạn là gì?",
            subtitle="Điều này giúp mình đưa ra lời khuyên phù hợp hơn",
            options=[
                CardOption(id="muscle_gain", label="Tăng cơ", icon="💪"),
                CardOption(id="weight_loss", label="Giảm cân", icon="⬇️"),
                CardOption(id="weight_gain", label="Tăng cân", icon="📈"),
                CardOption(id="maintain_shape", label="Giữ dáng", icon="⚖️"),
                CardOption(id="nutrient_supplement", label="Bổ sung chất", icon="🥗"),
                CardOption(id="medical_treatment", label="Điều trị bệnh lý", icon="🏥"),
                CardOption(id="balanced_lifestyle", label="Sinh hoạt điều độ", icon="🌿"),
            ],
            trigger_reason="missing_goal",
            skippable=True,
        )
        return card, "missing_goal"

    # Rule 3: No health_conditions + message mentions illness/diet restriction
    if (
        profile is not None
        and profile.health_conditions is None
        and "missing_health_conditions" not in fired
        and _has_health_keywords(user_message)
    ):
        card = ChatCard(
            card_id=str(uuid.uuid4()),
            card_type=CardType.CONFIRM,
            title="Bạn có tình trạng bệnh lý cần lưu ý không?",
            subtitle="Nếu có, mình sẽ điều chỉnh lời khuyên dinh dưỡng phù hợp hơn",
            options=None,
            trigger_reason="missing_health_conditions",
            skippable=True,
        )
        return card, "missing_health_conditions"

    # Rule 4: Calorie/meal plan request but no weight data
    if (
        profile is not None
        and getattr(profile, "current_weight_kg", None) is None
        and "missing_weight" not in fired
        and _has_plan_keywords(user_message)
    ):
        card = ChatCard(
            card_id=str(uuid.uuid4()),
            card_type=CardType.NUMBER_INPUT,
            title="Bạn nặng bao nhiêu kg?",
            subtitle="Cần biết cân nặng để tính lượng calories phù hợp",
            unit="kg",
            min_value=30.0,
            max_value=200.0,
            placeholder="Nhập cân nặng của bạn",
            trigger_reason="missing_weight",
            skippable=True,
        )
        return card, "missing_weight"

    return None, None  # No hard rule fired


def _is_nutrition_question(message: str) -> bool:
    keywords = [
        "ăn", "uống", "dinh dưỡng", "thực đơn", "calo", "protein",
        "giảm", "tăng", "chế độ", "bữa", "món", "thực phẩm", "gym",
    ]
    return any(kw in message.lower() for kw in keywords)


def _has_health_keywords(message: str) -> bool:
    keywords = [
        "tiểu đường", "huyết áp", "gout", "thận", "gan",
        "dị ứng", "bệnh", "thuốc", "điều trị", "kiêng",
    ]
    return any(kw in message.lower() for kw in keywords)


def _has_plan_keywords(message: str) -> bool:
    keywords = ["thực đơn", "kế hoạch ăn", "calories", "macro", "bữa ăn cho"]
    return any(kw in message.lower() for kw in keywords)
