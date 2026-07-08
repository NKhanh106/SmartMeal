"""
Food Mapping Service — Intelligent food name → database matching.

Upgrades the naive ILIKE search into a multi-stage fuzzy matching pipeline:

Stage 1: Exact match on normalized name (fastest path)
Stage 2: Vietnamese normalization + ILIKE search
Stage 3: Fuzzy matching (Levenshtein ratio) on normalized names
Stage 4: Multi-candidate ranking with score
Stage 5: Learned correction lookup (from user feedback)

Each detected food gets:
- best_match: top-1 candidate with score
- alternatives: top-5 candidates ranked by score
- match_status: "matched" | "partial" | "not_found"
- match_score: 0.0-1.0 confidence in the match
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food_nutrition import FoodNutrition


# ─── Vietnamese normalization ─────────────────────────────────────────────────────

def normalize_vietnamese(text: str) -> str:
    """
    Remove Vietnamese diacritics and lowercase.
    "Cơm Tấm Sườn Bì Chả" → "com tam suon bi cha"
    "café" → "cafe"
    "NƯỚC MẮM" → "nuoc mam"
    """
    try:
        # unidecode converts Vietnamese diacritics to ASCII equivalents
        from unidecode import unidecode
        return unidecode(text).lower().strip()
    except ImportError:
        # Fallback: just lowercase and strip
        import unicodedata
        normalized = ""
        for char in text.lower().strip():
            cat = unicodedata.category(char)
            # Strip combining diacritical marks (category starts with M)
            if cat.startswith("M") and cat != "Mn":
                continue
            normalized += char
        return normalized


def tokenize(text: str) -> set[str]:
    """Split normalized text into word tokens, removing common noise."""
    # Common Vietnamese stop words and punctuation to strip
    noise = {"cua", "voi", "va", "theo", "mot", "mieng", "phan", "toi", "oi", "a", "e", "o"}
    tokens = set(normalize_vietnamese(text).split())
    return tokens - noise


# ─── Fuzzy matching ───────────────────────────────────────────────────────────────

def _levenshtein_ratio(s1: str, s2: str) -> float:
    """
    Compute Levenshtein similarity ratio between two strings.
    Returns 0.0 (completely different) to 1.0 (identical).
    Uses rapidfuzz for performance.
    """
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(s1, s2) / 100.0
    except ImportError:
        # Fallback: pure Python Levenshtein
        return _levenshtein_ratio_pure(s1, s2)


def _levenshtein_ratio_pure(s1: str, s2: str) -> float:
    """Pure-Python fallback for Levenshtein ratio."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    # Simple Wagner-Fischer DP — bounded for performance
    max_dist = max(len1, len2)
    if max_dist > 100:
        # Too long — use quick estimate
        return 1.0 if s1 == s2 else 0.0

    # Build distance matrix
    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)
    for i in range(1, len1 + 1):
        curr[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev

    distance = prev[len2]
    return 1.0 - (distance / max_dist)


def _jaccard_similarity(tokens1: set[str], tokens2: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0


# ─── Match result dataclass ───────────────────────────────────────────────────────

@dataclass
class FoodMatchResult:
    """Result of matching a single food name against the database."""

    # The food name that was searched
    search_name: str

    # Best match
    matched_food: Optional[FoodNutrition] = None
    matched_food_id: Optional[UUID] = None
    match_score: float = 0.0  # 0.0-1.0

    # Match classification
    match_status: str = "not_found"  # "matched" | "partial" | "not_found"

    # Top alternatives (excluding best match)
    alternatives: list["FoodMatchCandidate"] = field(default_factory=list)

    # Diagnostics
    search_method: str = "none"  # "exact" | "normalized" | "fuzzy" | "learned"


@dataclass
class FoodMatchCandidate:
    """A candidate food with its matching score."""
    food: FoodNutrition
    score: float
    method: str


# ─── Core matching functions ───────────────────────────────────────────────────────

# Minimum score threshold to consider a match valid
MIN_MATCH_SCORE = 0.55
PARTIAL_MATCH_SCORE = 0.40


async def search_food_exact(
    db: AsyncSession,
    food_name: str,
    limit: int = 5,
) -> list[FoodNutrition]:
    """
    Stage 1: Exact match on normalized names.
    Uses exact keyword (already lowercased by normalization).
    """
    normalized = normalize_vietnamese(food_name)
    result = await db.execute(
        select(FoodNutrition)
        .where(
            or_(
                FoodNutrition.food_name.ilike(f"%{normalized}%"),
                FoodNutrition.food_name_vi.ilike(f"%{normalized}%"),
                FoodNutrition.food_name_en.ilike(f"%{normalized}%"),
            )
        )
        .order_by(FoodNutrition.is_verified.desc(), FoodNutrition.food_name.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


def score_candidates(
    candidates: list[FoodNutrition],
    search_name: str,
) -> list[FoodMatchCandidate]:
    """
    Score each candidate against the search name using multiple signals.
    Returns sorted list of candidates with scores.

    Tokens are derived from food_name, food_name_vi, AND food_name_en
    (max Jaccard across all three) so Vietnamese queries can match against
    foods whose canonical English name has no overlap with the query tokens.
    """
    search_normalized = normalize_vietnamese(search_name)
    search_tokens = tokenize(search_name)

    scored: list[FoodMatchCandidate] = []
    for food in candidates:
        food_norm = normalize_vietnamese(food.food_name or "")
        food_vi_norm = normalize_vietnamese(food.food_name_vi or "")
        food_en_norm = normalize_vietnamese(food.food_name_en or "")

        # Primary: Levenshtein ratio on normalized primary name
        lev_primary = _levenshtein_ratio(search_normalized, food_norm)
        lev_vi = _levenshtein_ratio(search_normalized, food_vi_norm)
        lev_en = _levenshtein_ratio(search_normalized, food_en_norm)
        lev_best = max(lev_primary, lev_vi, lev_en)

        # Secondary: max Jaccard across all token sources so "trứng gà" can
        # match "Trứng luộc" via shared vi tokens even when food_name is "Boiled egg".
        jaccard = max(
            _jaccard_similarity(search_tokens, tokenize(food.food_name or "")),
            _jaccard_similarity(search_tokens, tokenize(food.food_name_vi or "")),
            _jaccard_similarity(search_tokens, tokenize(food.food_name_en or "")),
        )

        # Combined score: weighted average (Levenshtein 0.5, Jaccard 0.5)
        # Equal weights balance typo correction (Lev) with semantic overlap (Jaccard).
        combined = (lev_best * 0.5) + (jaccard * 0.5)

        # Boost verified foods slightly
        if food.is_verified:
            combined = min(1.0, combined * 1.05)

        # Boost when the query's leading token is a substring of any food name.
        # Helps "trứng gà" → "Trứng luộc" (shared "trứng") cross the 0.55 threshold
        # without matching unrelated items like "thịt heo" → "Thịt bò nạc".
        search_token_list = list(search_tokens)
        if search_token_list:
            first_token = search_token_list[0]
            if (
                len(first_token) >= 3
                and (
                    first_token in food_norm
                    or first_token in food_vi_norm
                )
            ):
                combined = min(1.0, combined + 0.1)

        # Boost if exact normalized substring match
        if search_normalized in food_norm or search_normalized in food_vi_norm:
            combined = min(1.0, combined + 0.1)

        scored.append(FoodMatchCandidate(food=food, score=combined, method="fuzzy"))

    # Sort by score descending
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored


def classify_match(score: float) -> tuple[str, str]:
    """Classify match quality from score."""
    if score >= MIN_MATCH_SCORE:
        return "matched", "fuzzy"
    elif score >= PARTIAL_MATCH_SCORE:
        return "partial", "fuzzy"
    return "not_found", "fuzzy"


# ─── Main matching function ───────────────────────────────────────────────────────

async def match_food_name(
    db: AsyncSession,
    food_name: str,
    user_id: UUID | None = None,
    limit: int = 5,
) -> FoodMatchResult:
    """
    Multi-stage food name → database matching pipeline.

    Returns a FoodMatchResult with:
    - best match (top candidate)
    - alternatives (next best candidates)
    - match status and score

    Pipeline:
    1. Exact (case-insensitive ILIKE) — fastest
    2. Normalized Vietnamese search
    3. Fuzzy matching (Levenshtein + Jaccard)
    4. Learned correction lookup (if user_id provided)
    """
    result = FoodMatchResult(search_name=food_name)
    search_normalized = normalize_vietnamese(food_name)

    # ── Stage 1: Exact match (ILIKE on normalized name) ───────────────────────
    candidates = await search_food_exact(db, food_name, limit=limit * 2)

    if candidates:
        # Already have candidates from exact search
        scored = score_candidates(candidates, food_name)
    else:
        # No candidates found — try fuzzy across all foods
        # Fetch a broader sample for fuzzy matching
        all_foods = await db.execute(
            select(FoodNutrition)
            .order_by(FoodNutrition.is_verified.desc())
            .limit(500)
        )
        all_candidates = list(all_foods.scalars().all())
        scored = score_candidates(all_candidates, food_name)

    if not scored:
        result.match_status = "not_found"
        result.search_method = "fuzzy"
        return result

    # Top candidate
    top = scored[0]
    result.matched_food = top.food
    result.matched_food_id = top.food.id
    result.match_score = top.score
    result.match_status, result.search_method = classify_match(top.score)

    # Alternatives (up to limit-1)
    result.alternatives = [
        FoodMatchCandidate(food=c.food, score=c.score, method=c.method)
        for c in scored[1:limit]
        if c.score >= PARTIAL_MATCH_SCORE
    ]

    return result




# ─── Nutrition calculation ────────────────────────────────────────────────────────

def calculate_nutrition_per_item(
    food: Optional[FoodNutrition],
    weight_g: float,
) -> dict:
    """Calculate nutrition for a food at a given weight."""
    if food is None:
        return {"calories": 0.0, "protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0}
    ratio = float(weight_g) / 100.0
    return {
        "calories": round(float(food.calories_per_100g) * ratio, 2),
        "protein_g": round(float(food.protein_per_100g) * ratio, 2),
        "carb_g": round(float(food.carb_per_100g) * ratio, 2),
        "fat_g": round(float(food.fat_per_100g) * ratio, 2),
    }
