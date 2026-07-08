from enum import Enum
from dataclasses import dataclass


class ResponseDepth(str, Enum):
    QUICK = "quick"
    DEEP = "deep"
    EXPERT = "expert"


@dataclass
class DepthConfig:
    mode: ResponseDepth

    run_extractor: bool
    run_health_monitor: bool
    run_nutrition_advisor: bool
    run_fitness_coach: bool
    run_web_researcher: bool

    phase1_timeout: float
    phase2_timeout: float

    extractor_tokens: int
    health_tokens: int
    nutrition_tokens: int
    fitness_tokens: int
    final_response_tokens: int

    temperature: float
    system_prompt_variant: str

    response_style: str


DEPTH_CONFIGS = {
    ResponseDepth.QUICK: DepthConfig(
        mode=ResponseDepth.QUICK,

        run_extractor=True,
        run_health_monitor=False,
        run_nutrition_advisor=False,
        run_fitness_coach=False,
        run_web_researcher=False,

        phase1_timeout=0.0,
        phase2_timeout=0.0,

        extractor_tokens=400,
        health_tokens=0,
        nutrition_tokens=0,
        fitness_tokens=0,
        final_response_tokens=1000,

        temperature=0.4,
        system_prompt_variant="quick",
        response_style=(
            "Trả lời NGẮN GỌN và TRỰC TIẾP. "
            "Tối đa 2-3 câu hoặc 1 danh sách ngắn. "
            "Không giải thích dài dòng. "
            "Nếu cần thông tin thêm, hỏi 1 câu ngắn thôi."
        ),
    ),

    ResponseDepth.DEEP: DepthConfig(
        mode=ResponseDepth.DEEP,

        run_extractor=True,
        run_health_monitor=True,
        run_nutrition_advisor=True,
        run_fitness_coach=True,
        run_web_researcher=False,

        phase1_timeout=12.0,
        phase2_timeout=8.0,

        extractor_tokens=600,
        health_tokens=1000,
        nutrition_tokens=1000,
        fitness_tokens=800,
        final_response_tokens=1500,

        temperature=0.5,
        system_prompt_variant="deep",
        response_style=(
            "Trả lời CÂN BẰNG giữa chi tiết và dễ đọc. "
            "3-5 đoạn hoặc danh sách có giải thích. "
            "Đưa ra lý do cho mỗi gợi ý. "
            "Có thể hỏi thêm 1-2 câu để làm rõ nếu cần."
        ),
    ),

    ResponseDepth.EXPERT: DepthConfig(
        mode=ResponseDepth.EXPERT,

        run_extractor=True,
        run_health_monitor=True,
        run_nutrition_advisor=True,
        run_fitness_coach=True,
        run_web_researcher=True,

        phase1_timeout=20.0,
        phase2_timeout=15.0,

        extractor_tokens=800,
        health_tokens=1500,
        nutrition_tokens=1500,
        fitness_tokens=1200,
        final_response_tokens=2000,

        temperature=0.6,
        system_prompt_variant="expert",
        response_style=(
            "Trả lời với ĐỘ SÂU CHUYÊN GIA. "
            "Phân tích toàn diện từ nhiều góc độ: y tế, dinh dưỡng, vận động. "
            "Đưa ra kế hoạch cụ thể với các bước rõ ràng. "
            "Trích dẫn cơ sở khoa học nếu có từ nghiên cứu. "
            "Luôn cảnh báo khi cần gặp chuyên gia thực sự. "
            "Có thể trả lời dài — ưu tiên đầy đủ và chính xác hơn ngắn gọn."
        ),
    ),
}


def get_depth_config(mode: str) -> DepthConfig:
    try:
        depth = ResponseDepth(mode)
        return DEPTH_CONFIGS[depth]
    except ValueError:
        return DEPTH_CONFIGS[ResponseDepth.DEEP]
