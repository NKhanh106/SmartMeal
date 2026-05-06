"""
AI Orchestrator — the central brain of the SmartMeal AI system.

This module implements intelligent request routing, confidence-based logic,
retry strategies, and multi-step pipeline orchestration.

Key principles:
1. CONFIGURED CONFIDENCE THRESHOLDS — not arbitrary
2. RETRY WITH EXPONENTIAL BACKOFF — transient failures recover
3. CIRCUIT BREAKER — block calls when provider is continuously failing
4. SINGLE RESPONSIBILITY — orchestrator delegates, doesn't implement

Usage:
    from app.ai.orchestrator import ai_orchestrator

    # Food recognition with confidence routing
    result = await ai_orchestrator.recognize_food_image(
        db=db,
        user_id=user_id,
        image_bytes=image_bytes,
        mime_type=mime_type,
        meal_type=meal_type,
    )

    if result.confidence_level == ConfidenceLevel.LOW:
        # Trigger human review flow
        ...
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.circuit_breaker import gemini_circuit, groq_circuit
from app.core.config import settings
from app.services.learning_service import get_learned_correction

logger = logging.getLogger(__name__)

# ─── Confidence Levels ─────────────────────────────────────────────────────────────

class ConfidenceLevel(str, Enum):
    HIGH = "high"       # >= 0.7 — auto-accept, confident
    MEDIUM = "medium"   # 0.4-0.69 — review suggested, proceed with caution
    LOW = "low"         # < 0.4 — flag for review, might be wrong


@dataclass
class RecognitionResult:
    """Standardized result from any AI recognition pipeline."""
    overall_confidence: float
    confidence_level: ConfidenceLevel
    notes: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: int = 0
    retry_count: int = 0
    items: list["RecognizedFoodItem"] = field(default_factory=list)


@dataclass
class RecognizedFoodItem:
    """A single recognized food item with full metadata."""
    food_name: str
    weight_g: float
    confidence: float
    match_score: float | None = None
    match_status: str | None = None
    nutrition: dict[str, float] | None = None
    requires_review: bool = False
    review_reason: str | None = None


# ─── Orchestrator ─────────────────────────────────────────────────────────────────

class AIOrchestrator:
    """
    Central AI brain that:

    1. Routes food recognition requests through the pipeline
    2. Evaluates confidence levels and decides auto-accept vs review
    3. Applies learned corrections from the feedback loop
    4. Manages retry logic with exponential backoff
    5. Provides fallback provider chains
    """

    # ─── Vision-aware fallback chain ─────────────────────────────────────────────
    # Only providers that actually support image input should handle vision tasks.
    # Groq's vision_model does support vision, but Gemini is preferred for meal
    # recognition due to superior Vietnamese food understanding. If Gemini fails,
    # Groq is tried as a genuine fallback (it has a real vision model). If Groq
    # also fails, we surface a clear error rather than crashing silently.
    _VISION_PROVIDERS = frozenset({"gemini", "groq"})

    def __init__(self):
        self.primary_provider = settings.AI_MEAL_PROVIDER
        self.fallback_provider = (
            "groq" if settings.AI_MEAL_PROVIDER == "gemini" else "gemini"
        )

        # Confidence thresholds
        self.AUTO_ACCEPT_THRESHOLD = 0.70  # >= 0.7 → HIGH
        self.REVIEW_THRESHOLD = 0.40       # >= 0.4 → MEDIUM, else LOW

        # Retry config
        self.max_retries = 2
        self.base_delay = 1.0  # seconds

    async def recognize_food_image(
        self,
        db: AsyncSession,
        user_id: UUID,
        image_bytes: bytes,
        mime_type: str,
        meal_type: str,
    ) -> RecognitionResult:
        """
        Full food recognition pipeline with retry + fallback:

        1. Call AI vision model (with retry + fallback provider)
        2. Map each food to nutrition DB (fuzzy matching happens in the service)
        3. Apply learned corrections from user's past corrections
        4. Classify confidence level for each item
        5. Mark items requiring human review
        """
        preview = None
        raw_response = None
        latency_ms = 0
        retry_count = 0
        used_provider = self.primary_provider
        last_error: Exception | None = None
        success = False

        # Vision provider chain: try primary, then fallback.
        # Both gemini and groq have real vision models, so both are valid here.
        _raw_chain = [self.primary_provider]
        if self.fallback_provider in self._VISION_PROVIDERS:
            _raw_chain.append(self.fallback_provider)
        # Deduplicate in case primary == fallback
        seen: set[str] = set()
        providers_to_try: list[str] = []
        for p in _raw_chain:
            if p not in seen:
                seen.add(p)
                providers_to_try.append(p)

        for attempt in range(self.max_retries + 1):
            for provider in providers_to_try:
                if attempt > 0 and provider == self.primary_provider:
                    continue

                used_provider = provider
                retry_count = attempt

                try:
                    old_provider = settings.AI_MEAL_PROVIDER
                    settings.AI_MEAL_PROVIDER = provider

                    try:
                        preview, raw_response, latency_ms = await self._call_meal_preview(
                            db=db,
                            user_id=user_id,
                            image_bytes=image_bytes,
                            mime_type=mime_type,
                            meal_type=meal_type,
                        )
                    finally:
                        settings.AI_MEAL_PROVIDER = old_provider

                    success = True
                    break

                except Exception as exc:
                    last_error = exc
                    settings.AI_MEAL_PROVIDER = self.primary_provider

                    if attempt < self.max_retries:
                        await asyncio.sleep(self.base_delay * (2 ** attempt))

            if success:
                break

        if not success or preview is None:
            raise last_error or RuntimeError("AI Orchestrator: no preview after all retries")

        # ── Step 2: Enrich items with learned corrections ─────────────────────────
        for item in preview.items:
            learned = await get_learned_correction(db, user_id, item.detected_food_name)
            # learned = (corrected_food_id, consistency) if found, else None
            # The match_food_name pipeline can use this to prioritize corrections
            if learned:
                # Store in item's metadata for downstream use
                item.learned_correction_id = str(learned[0])
                item.learned_correction_confidence = learned[1]

        # ── Step 3: Classify confidence level ──────────────────────────────────────
        overall_confidence = float(preview.overall_confidence)
        confidence_level = self._classify_confidence(overall_confidence)

        # ── Step 4: Build recognized items with review flags ─────────────────────────
        recognized_items: list[RecognizedFoodItem] = []
        for item in preview.items:
            recognized = RecognizedFoodItem(
                food_name=item.detected_food_name,
                weight_g=item.estimated_weight_g,
                confidence=float(item.confidence),
                match_score=float(item.match_score) if item.match_score else None,
                match_status=item.match_status,
                nutrition=(
                    {"calories": item.calories, "protein_g": item.protein_g,
                     "carb_g": item.carb_g, "fat_g": item.fat_g}
                    if item.calories is not None else None
                ),
            )

            # Flag items needing review
            if item.confidence < self.REVIEW_THRESHOLD:
                recognized.requires_review = True
                recognized.review_reason = (
                    f"AI confidence is low ({item.confidence:.0%}). Please verify food name and weight."
                )
            elif item.estimated_weight_g > 2000:
                recognized.requires_review = True
                recognized.review_reason = (
                    f"Weight ({item.estimated_weight_g:.0f}g) seems unusually high. Verify before saving."
                )
            elif item.match_status == "not_found":
                recognized.requires_review = True
                recognized.review_reason = (
                    "Food not found in database. Please manually enter nutrition data."
                )

            recognized_items.append(recognized)

        # Determine model name
        model_name = (
            settings.GEMINI_MODEL
            if used_provider == "gemini"
            else settings.GROQ_VISION_MODEL
        )

        return RecognitionResult(
            overall_confidence=overall_confidence,
            confidence_level=confidence_level,
            notes=getattr(preview, "notes", None),
            provider=used_provider,
            model=model_name,
            latency_ms=latency_ms,
            retry_count=retry_count,
            items=recognized_items,
        )

    async def _call_meal_preview(
        self,
        db: AsyncSession,
        user_id: UUID,
        image_bytes: bytes,
        mime_type: str,
        meal_type: str,
    ):
        """Call meal preview through circuit breaker with provider fallback."""
        from app.services.ai_meal_update_service import preview_meal_from_image

        # Select circuit based on primary provider
        primary_circuit = gemini_circuit if self.primary_provider == "gemini" else groq_circuit
        fallback_circuit = groq_circuit if self.primary_provider == "gemini" else gemini_circuit

        # Try primary first
        if primary_circuit.is_available():
            try:
                return await primary_circuit.call(
                    preview_meal_from_image,
                    db=db,
                    user_id=user_id,
                    meal_type=meal_type,
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                )
            except RuntimeError:
                # Circuit is open — fall through to fallback
                logger.warning("Primary circuit [%s] is OPEN, trying fallback", self.primary_provider)
            except Exception as exc:
                logger.warning("Primary provider failed: %s", exc)

        # Fallback to secondary provider
        if fallback_circuit.is_available():
            try:
                logger.info("Using fallback provider for meal preview")
                return await fallback_circuit.call(
                    preview_meal_from_image,
                    db=db,
                    user_id=user_id,
                    meal_type=meal_type,
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                )
            except RuntimeError:
                raise HTTPException(
                    status_code=503,
                    detail="All AI providers are temporarily unavailable. Please try again in ~60 seconds."
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"All AI providers failed: {exc}"
                )

        raise HTTPException(
            status_code=503,
            detail="All AI circuits are OPEN. Please try again later."
        )

    def _classify_confidence(self, confidence: float) -> ConfidenceLevel:
        """Classify confidence into discrete levels."""
        if confidence >= self.AUTO_ACCEPT_THRESHOLD:
            return ConfidenceLevel.HIGH
        elif confidence >= self.REVIEW_THRESHOLD:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def get_confidence_display(self, level: ConfidenceLevel) -> tuple[str, str]:
        """Get (label, tailwind_color_class) for a confidence level."""
        if level == ConfidenceLevel.HIGH:
            return "Tin cậy", "text-green-600"
        elif level == ConfidenceLevel.MEDIUM:
            return "Cần kiểm tra", "text-yellow-600"
        else:
            return "Không chắc chắn", "text-red-600"


# Singleton instance
ai_orchestrator = AIOrchestrator()
