def build_chat_title(text: str, max_chars: int = 40, max_words: int = 6) -> str:
    if not text or not text.strip():
        return "Cuoc tro chuyen moi"

    cleaned = text.strip()
    words = cleaned.split()

    # Step 1: enforce word limit
    if len(words) > max_words:
        truncated = " ".join(words[:max_words])
        add_ellipsis = True
    else:
        truncated = cleaned
        add_ellipsis = len(words) == max_words and len(cleaned) > max_chars

    # Step 2: enforce char limit
    if len(truncated) > max_chars:
        truncated = truncated[:max_chars - 3].rstrip()
        add_ellipsis = True

    if add_ellipsis and not truncated.endswith("..."):
        if len(truncated) + 3 <= max_chars:
            truncated = truncated + "..."

    return truncated
