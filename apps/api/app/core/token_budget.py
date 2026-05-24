"""
Token budget management utilities to prevent context overflow in AI prompts.

Use truncate_to_token_budget() to limit any text block to an approximate
token budget, and build_context_within_budget() to construct a full prompt
context string that fits within a target budget.
"""

from __future__ import annotations

MAX_CONTEXT_TOKENS = 4000  # leave room for output

# Vietnamese text uses ~2.5-3 chars/token with subword tokenization
# Using 3 as conservative-but-accurate estimate for Vietnamese
_CHARS_PER_TOKEN = 3


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    Vietnamese averages ~3 chars/token, English ~4.
    """
    vietnamese_chars = sum(1 for c in text if ord(c) > 127)
    ratio = vietnamese_chars / max(len(text), 1)

    if ratio > 0.3:  # Mostly Vietnamese
        chars_per_token = 3.0
    else:  # Mostly English
        chars_per_token = 4.0

    return int(len(text) / chars_per_token)


def truncate_to_token_budget(
    text: str,
    budget: int,
    truncate_from: str = "middle",  # "start" | "middle" | "end"
) -> str:
    """
    Truncate text to approximate token budget.

    Args:
        text: The text to truncate.
        budget: Maximum tokens to keep.
        truncate_from: Where to cut. "middle" preserves start + end (most important).

    Returns:
        Truncated string within budget.
    """
    max_chars = budget * _CHARS_PER_TOKEN

    if len(text) <= max_chars:
        return text

    if truncate_from == "end":
        return text[:max_chars]
    elif truncate_from == "start":
        return text[-max_chars:]
    else:  # middle — preserve beginning and end
        half = max_chars // 2
        return text[:half] + "\n...[truncated]...\n" + text[-half:]


def build_context_within_budget(
    sections: list[tuple[str, str, int]],
    total_budget: int = MAX_CONTEXT_TOKENS,
) -> str:
    """
    Build a context string fitting within a token budget.

    Sections are sorted by priority (ascending) — highest priority first.
    Lower-priority sections are dropped first when budget is exceeded.

    Args:
        sections: List of (name, content, priority) tuples.
                  Higher priority number = more important (included first).
        total_budget: Maximum tokens for the entire context.

    Returns:
        Context string within budget.
    """
    sorted_sections = sorted(sections, key=lambda x: x[2], reverse=True)
    result: list[str] = []
    used_chars = 0

    for name, content, _priority in sorted_sections:
        section_tokens = len(content) // _CHARS_PER_TOKEN
        available_tokens = total_budget - (used_chars // _CHARS_PER_TOKEN)

        if section_tokens <= available_tokens:
            result.append(f"[{name}]\n{content}")
            used_chars += len(content) + len(name) + 2
        else:
            remaining = total_budget - (used_chars // _CHARS_PER_TOKEN)
            if remaining > 100:
                truncated = truncate_to_token_budget(content, remaining, "end")
                result.append(f"[{name}]\n{truncated}")
            break

    return "\n\n".join(result)
