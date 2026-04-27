def build_chat_title(first_message: str, max_length: int = 60) -> str:
    title = first_message.strip().replace("\n", " ")
    if len(title) <= max_length:
        return title
    return title[:max_length].rstrip() + "..."
