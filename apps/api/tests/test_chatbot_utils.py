import pytest
from app.chatbot.utils import build_chat_title


class TestBuildChatTitle:
    def test_short_text_unchanged(self):
        result = build_chat_title("Xin chào")
        assert result == "Xin chào"
        assert len(result) <= 40

    def test_exactly_6_words_kept(self):
        result = build_chat_title("tôi muốn ăn gì hôm nay")
        words = result.rstrip("...").split()
        # 6 words — at the word limit, all 6 are kept (no ellipsis)
        assert len(words) == 6
        assert len(result) <= 40

    def test_truncates_to_6_words(self):
        result = build_chat_title("tôi muốn ăn gì hôm nay để tăng cơ bắp hiệu quả")
        words = result.rstrip("...").split()
        assert len(words) == 6

    def test_enforces_40_char_limit(self):
        result = build_chat_title("a" * 100)
        assert len(result) <= 40

    def test_long_words_truncated_with_ellipsis(self):
        result = build_chat_title("tôi muốn ăn gì hôm nay để tăng cơ bắp hiệu quả")
        assert len(result) <= 40
        assert result.endswith("...")

    def test_empty_string_returns_default(self):
        result = build_chat_title("")
        assert result == "Cuoc tro chuyen moi"

    def test_whitespace_only_returns_default(self):
        result = build_chat_title("   ")
        assert result == "Cuoc tro chuyen moi"

    def test_preserves_short_text(self):
        result = build_chat_title("phở bò cho bữa trưa")
        assert result == "phở bò cho bữa trưa"

    def test_short_text_with_long_words(self):
        result = build_chat_title("a" * 50)
        assert len(result) <= 40
        assert result.endswith("...")
