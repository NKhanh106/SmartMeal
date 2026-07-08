CHATBOT_PROMPT_VERSION = "chatbot_v1"

import json

CHATBOT_SYSTEM_PROMPT = """
Bạn là AI Coach của SmartMeal — hỗ trợ dinh dưỡng và luyện tập cá nhân hóa.

VAI TRÒ:
- Trả lời ngắn gọn, thực tế, dựa trên dữ liệu cá nhân trong context.
- Ưu tiên mục tiêu hiện tại của người dùng.
- Nếu hỏi ăn gì → dựa vào lượng calo/macro đã ăn hôm nay.
- Nếu hỏi tập gì → dựa vào mục tiêu và gợi ý gần nhất.

AN TOÀN:
- Không chẩn đoán bệnh, không thay thế tư vấn bác sĩ.
- Không khuyến nghị nhịn ăn cực đoan hoặc tập quá sức.
- Không bịa số liệu nếu context không có.

TRẢ LỜI:
- Bằng tiếng Việt, ngắn gọn, có hành động cụ thể.
- Ưu tiên 2-4 gợi ý dạng bullet.
- Sử dụng conversation_insights trong context để cá nhân hóa.

INTERACTIVE CARDS (tool: ask_user):
Dùng khi: cần số cụ thể (cân nặng, khẩu phần), cần xác nhận trước hành động không hoàn tác.
Không dùng khi: đã có thông tin cần thiết, câu hỏi trả lời tự nhiên được.
Tối đa 1 card mỗi phản hồi. Khi dùng → viết 1 câu ngắn rồi gọi tool, không trả lời dài.
"""


def build_chatbot_user_prompt(context: dict) -> str:
    """
    JSON-encode the context dict so that any residual injection payloads
    surviving sanitize_for_prompt (e.g. a "[filtered]" replacement string
    containing adversarial text) are escaped inside a JSON string literal and
    cannot break out of the template.

    The AI receives the context as a JSON string, which is unambiguous regardless
    of what characters are embedded in field values.

    Internal fields (keys starting with "_" — e.g. _profile_object holding
    the live SQLAlchemy ORM UserProfile used by hard-rule card triggers)
    are stripped before serialization to avoid TypeError on json.dumps.
    """
    serializable = {k: v for k, v in context.items() if not k.startswith("_")}
    # indent=None → compact; ensure_ascii=False → preserves Vietnamese diacritics
    context_json = json.dumps(serializable, indent=None, ensure_ascii=False)
    # Temporary diagnostic — per-top-level-key size breakdown to identify
    # which field(s) dominate the prompt. Remove after 413 issue is resolved.
    import sys as _sys
    _sizes = {k: len(json.dumps(v, ensure_ascii=False)) for k, v in serializable.items()}
    _top = sorted(_sizes.items(), key=lambda kv: kv[1], reverse=True)[:8]
    print(f"[prompt-debug] per-key chars (top 8): {_top}", file=_sys.stderr, flush=True)
    return f"""Dưới đây là context cá nhân hóa của người dùng trong hệ thống SmartMeal.

Context:
{context_json}

Hãy trả lời câu hỏi của người dùng dựa trên context trên.
"""


INSIGHT_EXTRACTION_SYSTEM_PROMPT = """
Bạn là chuyên gia dinh dưỡng SmartMeal. Nhiệm vụ: đọc cuộc trò chuyện, trích xuất thông tin mới và trả về JSON theo schema.
Chỉ trả JSON hợp lệ, không giải thích thêm.
"""


def build_insight_extraction_prompt(recent_messages: list[dict]) -> str:
    """
    Xây dựng prompt để AI trích xuất insights từ danh sách tin nhắn.
    """
    messages_lines = []
    for msg in recent_messages:
        role_label = msg["role"].upper()
        content = msg["content"]
        messages_lines.append(f"[{role_label}] {content}")
    messages_text = "\n\n".join(messages_lines)

    return (
        "Doc cuoc tro chuyen sau giua nguoi dung va AI SmartMeal:\n\n"
        + messages_text
        + """

Tu cuoc tro chuyen tren, trich xuat cac thong tin moi, quan trong chua duoc ghi nhan, hoac thay doi so voi truoc do. Tra ve JSON theo schema.

Cac loai insights:
- diet_preference: So thich / khong thich mon an, che do an chay, ...
- health_constraint: Di ung, benh ly, han che an uong gi
- fitness_note: Tan suat tap luyen, loai bai tap, han che ve suc khoe
- goal_note: Thay doi muc tieu, can nang, loi song
- general: Thong tin chung khac

Neu khong co thong tin moi nao, tra ve insights rong va has_new_information=false.
Neu co thong tin moi, tra ve danh sach insights va has_new_information=true.

Moi key phai ngan gon, khong dau cach, chi chu cai thuong va so.
Vi du: preferred_cuisine, allergy_soy, exercise_freq, goal_weight_loss

Moi value phai la mot cau ngan, cu the.
Vi du: Thich mon an Viet Nam han che mon cay, Tap gym 3 lan/tuan

Moi summary phai la mot cau tieng Viet tu nhien, dung lam context cho doan hoi thoai sau.
Vi du: Nguoi dung thich an rau xanh, khong an thit do"""
    )
