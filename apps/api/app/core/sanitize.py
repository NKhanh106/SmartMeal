"""
Input sanitization utilities for AI prompt injection prevention.

All user-provided text injected into AI prompts should pass through
sanitize_for_prompt() to strip control characters and known injection
patterns before it enters the prompt.
"""

from __future__ import annotations

import re
import unicodedata

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # Prompt override attempts
    re.compile(r"ignore\s+(previous|above|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"forget\s+everything", re.IGNORECASE),
    re.compile(r"disregard\s+(all|previous|above)", re.IGNORECASE),
    # Special token injection
    re.compile(r"<\|.*?\|>"),
    # Instruction tag injection (Llama-style)
    re.compile(r"\[INST\].*?\[/INST\]", re.IGNORECASE | re.DOTALL),
    # Markdown / XML prompt injection
    re.compile(r"###\s*(instruction|system|human|assistant)", re.IGNORECASE),
    re.compile(r"<(?:\/?)(?:system|user|assistant)(?:\s[^>]*)?>", re.IGNORECASE),
    # Encoding tricks
    re.compile(r"\x00+"),  # null bytes
]


def sanitize_for_prompt(
    text: str,
    max_length: int = 500,
    truncate_from: str = "end",
) -> str:
    """
    Sanitize user input before injecting into AI prompts.

    Removes:
    - Known prompt injection patterns (after NFKC normalization)
    - Control characters and null bytes
    - Excessively long inputs (truncated to max_length)

    Processing order (FIX-7):
      1. Unicode NFKC normalization — defeats homoglyph / mixed-script tricks
      2. Strip null / control chars
      3. Apply ALL INJECTION_PATTERNS regex filters
      4. Truncate to max_length (post-filter, so boundary-spanning patterns
         cannot slip through)

    Args:
        text: Raw user input string
        max_length: Maximum characters to keep (default 500).
                    Prevents token budget exhaustion attacks.
        truncate_from: Where to cut when truncating.
                        "end"    → keep prefix (default, safest for injection defense)
                        "start"  → keep suffix
                        "middle" → keep head+tail, drop middle

    Returns:
        Sanitized string safe for prompt injection.
    """
    if not text:
        return ""

    # FIX-7 Step 1 (V-9): Normalize Unicode — collapses homoglyphs
    # e.g. Cyrillic 'і' → Latin 'i', full-width → half-width, etc.
    text = unicodedata.normalize("NFKC", text)

    # FIX-7 Step 2: Strip null bytes and other control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # FIX-7 Step 3 (V-1, V-3): Apply ALL injection filters BEFORE truncation.
    # This prevents boundary-spanning payloads from slipping through the cut.
    for pattern in INJECTION_PATTERNS:
        text = pattern.sub("[filtered]", text)

    # FIX-7 Step 4: Truncate only after the text is clean
    if len(text) <= max_length:
        return text.strip()

    if truncate_from == "end":
        text = text[:max_length]
    elif truncate_from == "middle":
        half = max_length // 2
        text = f"{text[:half]}\n...[truncated]...\n{text[-half:]}"
    else:  # "start"
        text = text[-max_length:]

    return text


def sanitize_food_name(name: str) -> str:
    """
    Sanitize food names for DB storage and AI prompts.

    Allows: Unicode letters, numbers, spaces, Vietnamese diacritics,
    and common punctuation: . , ( ) - _
    """
    if not name:
        return ""
    # Allow printable Unicode including Vietnamese: \u00C0-\u024F \u1EA0-\u1EF9
    cleaned = re.sub(r"[^\w\s\u00C0-\u024F\u1EA0-\u1EF9.,()-]", "", name)
    return cleaned[:200].strip()
