"""
Agent 5 — Web Researcher.

Runs ON-DEMAND only — triggered by the orchestrator when the user asks
for research-based information, latest findings, or fact-checking.

Rate limiting: max 3 searches per user per day, tracked in agent_runs table.
Results are cached in Redis for 24h (same query → cached result).

Trusted sources:
- Medical: who.int, pubmed.ncbi.nlm.nih.gov, vinmec.com, suckhoedoisong.vn, bacsidanang.vn
- Nutrition: healthline.com, examine.com, nutritionfacts.org
"""

import asyncio
import hashlib
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.ai.circuit_breaker import groq_circuit
from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.core.sanitize import sanitize_for_prompt
from app.models.agent_run import AgentRun
from tavily import AsyncTavilyClient

logger = logging.getLogger(__name__)

# ── Trigger detection ─────────────────────────────────────────────────────────

RESEARCH_TRIGGERS = [
    "mới nhất",
    "nghiên cứu",
    "có thật không",
    "khoa học nói",
    "so sánh",
    "review",
    "tốt nhất hiện nay",
    "bài báo",
    "nghiên cứu cho thấy",
    "theo nghiên cứu",
    "y khoa",
    "bằng chứng khoa học",
    "evidence-based",
    "is it safe",
    "scientific evidence",
    "newest",
    "latest research",
    "best supplement",
]

UNCONFIDENCE_FOOD_TRIGGERS = [
    "supplement",
    "vitamin",
    "thực phẩm chức năng",
    "thuốc bổ",
    "probiotic",
    "prebiotic",
    "keto diet",
    "intermittent fasting",
    "carnivore",
    "vegan diet",
    "dash diet",
    "mediterranean diet trend",
    "new diet trend",
    "ai làm gì",
    "ai có thể",
    "whey protein tốt nhất",
]


def should_trigger_web_research(message: str) -> bool:
    """Return True if the user message warrants a web research agent."""
    msg_lower = message.lower().strip()

    # Keyword-based triggers
    for trigger in RESEARCH_TRIGGERS:
        if trigger.lower() in msg_lower:
            return True

    # Fact-checking pattern
    if "có thật không" in msg_lower or "thật không" in msg_lower:
        return True

    return False


def needs_low_confidence_research(message: str) -> bool:
    """Return True if message mentions topics AI has low confidence about."""
    msg_lower = message.lower()
    return any(t in msg_lower for t in UNCONFIDENCE_FOOD_TRIGGERS)


# ── Rate limiting helpers ───────────────────────────────────────────────────────

WEB_RESEARCH_MAX_PER_DAY = 3
_WEB_RESEARCH_TTL_SECONDS = 86400  # 24 hours


async def count_agent_runs_today(
    user_id: str,
    agent_name: str,
    db: AsyncSession,
) -> int:
    """Count how many times agent_name ran for this user today."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    result = await db.execute(
        select(func.count(AgentRun.id))
        .where(
            AgentRun.user_id == user_id,
            AgentRun.agent_name == agent_name,
            AgentRun.status.in_(["completed", "failed"]),
            AgentRun.created_at >= today_start,
        )
    )
    return result.scalar() or 0


# ── Search query generation ───────────────────────────────────────────────────

RESEARCHER_SYSTEM_PROMPT = """Bạn là một chuyên gia nghiên cứu y khoa và dinh dưỡng.

Nhiệm vụ: Chuyển đổi câu hỏi của người dùng thành một truy vấn tìm kiếm web tối ưu.

QUY TẮC:
1. Luôn dịch sang tiếng Anh cho web search
2. Trọng tâm: dinh dưỡng, sức khỏe, y khoa
3. Giữ truy vấn ngắn gọn (dưới 80 ký tự)
4. KHÔNG thêm từ như "research", "study", "article" — chỉ cần từ khóa chính
5. Tập trung vào khía cạnh khoa học, không phải thương mại

Ví dụ:
- "Phở bò có tốt không khi bị tiêu chảy?" → "pho beef diarrhea safe eat"
- "Vitamin D có cần thiết không?" → "vitamin D health benefits evidence"
- "Chế độ ăn keto có an toàn không?" → "ketogenic diet safety evidence"
- "Probiotic tốt cho đường ruột không?" → "probiotics gut health scientific evidence"

Trả lời CHỈ bằng truy vấn tìm kiếm, không có giải thích."""


def _build_research_cache_key(user_id: str, query: str) -> str:
    """Create a deterministic cache key for a web research query, fresh per day."""
    today = date.today().isoformat()  # "2026-05-23"
    raw = f"{user_id}:{query}:{today}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"smartmeal:web_research:{h}"


# ── Trusted sources ────────────────────────────────────────────────────────────

TRUSTED_SOURCES = [
    "who.int",
    "healthline.com",
    "pubmed.ncbi.nlm.nih.gov",
    "vinmec.com",
    "suckhoedoisong.vn",
    "bacsidanang.vn",
    "examine.com",
    "nutritionfacts.org",
    "cdc.gov",
    "mayoclinic.org",
    "nih.gov",
    "webmd.com",
    "medicalnewstoday.com",
]

# Domain whitelist for Tavily API (passed as include_domains)
TRUSTED_DOMAINS = list(TRUSTED_SOURCES)

# Source quality labels
SOURCE_QUALITY = {
    "pubmed.ncbi.nlm.nih.gov": {"label": "PubMed", "type": "academic", "tier": 1},
    "who.int": {"label": "WHO", "type": "health_authority", "tier": 1},
    "cdc.gov": {"label": "CDC", "type": "health_authority", "tier": 1},
    "mayoclinic.org": {"label": "Mayo Clinic", "type": "hospital", "tier": 1},
    "nih.gov": {"label": "NIH", "type": "health_authority", "tier": 1},
    "vinmec.com": {"label": "Vinmec", "type": "hospital", "tier": 2},
    "healthline.com": {"label": "Healthline", "type": "health_media", "tier": 2},
    "medicalnewstoday.com": {"label": "Medical News Today", "type": "health_media", "tier": 2},
    "examine.com": {"label": "Examine.com", "type": "nutrition_science", "tier": 2},
    "nutritionfacts.org": {"label": "NutritionFacts.org", "type": "nutrition_media", "tier": 2},
    "suckhoedoisong.vn": {"label": "Sức Khỏe Đời Sống", "type": "health_media", "tier": 3},
    "bacsidanang.vn": {"label": "Bác Sĩ Đà Nẵng", "type": "health_media", "tier": 3},
    "webmd.com": {"label": "WebMD", "type": "health_media", "tier": 3},
}


def _source_is_trusted(url: str) -> tuple[bool, str | None]:
    """Check if a URL is from a trusted source. Returns (is_trusted, source_key)."""
    url_lower = url.lower()
    for source in TRUSTED_SOURCES:
        if source in url_lower:
            source_key = next(
                (k for k in SOURCE_QUALITY if k in url_lower),
                source,
            )
            return True, source_key
    return False, None


def _extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    match = re.search(r"https?://([^/]+)", url, re.IGNORECASE)
    if match:
        domain = match.group(1)
        return domain.removeprefix("www.")
    return url


# ── Web Researcher Agent ───────────────────────────────────────────────────────

FINDINGS_SCHEMA = """{
  "findings": [
    {
      "source_name": "Tên nguồn hiển thị (tiếng Việt)",
      "source_url": "https://...",
      "source_type": "academic | health_authority | hospital | health_media | nutrition_media",
      "key_finding": "Khám phá/claim chính từ nguồn (1-2 câu, tiếng Việt)",
      "relevance_score": 0.0-1.0,
      "date_published": "YYYY-MM-DD hoặc null"
    }
  ],
  "search_summary": "Tóm tắt ngắn gọn 2-3 câu về những gì tìm thấy (tiếng Việt)",
  "confidence": 0.0-1.0,
  "limitations": "Hạn chế của nghiên cứu (1-2 câu) hoặc chuỗi rỗng",
  "user_facing_summary": "1-2 câu tóm tắt thân thiện cho người dùng (tiếng Việt)"
}"""


class WebResearcherAgent(BaseAgent):
    name = "web_researcher"

    async def execute(
        self,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResult:
        run = self._log_start(
            context=context,
            trigger="web_research_requested",
            input_summary=context.current_message[:200],
            db=db,
        )

        try:
            # ── 1. Rate limit check ─────────────────────────────────────────────
            user_id_str = str(context.user.id)
            today_count = await count_agent_runs_today(
                user_id=user_id_str,
                agent_name=self.name,
                db=db,
            )

            if today_count >= WEB_RESEARCH_MAX_PER_DAY:
                result = AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="web_research",
                    content={"findings": [], "rate_limited": True},
                    confidence=1.0,
                    priority=10,
                    text_for_orchestrator=(
                        "BAN da su dung het 3 luot tra cuu web hom nay. "
                        "Vui lòng quay lại vào ngày mai."
                    ),
                    memory_updates={},
                )
                await self._log_complete(run, result, db, output_summary="Rate limited")
                return result

            # ── 2. Generate search query ─────────────────────────────────────────
            search_query = await self._generate_search_query(context.current_message)

            # ── 3. Check Redis cache ───────────────────────────────────────────
            cache_key = _build_research_cache_key(user_id_str, search_query)
            cached = await cache_get(cache_key)
            if cached:
                result = AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="web_research",
                    content=cached,
                    confidence=cached.get("confidence", 0.5),
                    priority=7,
                    text_for_orchestrator=self._build_text_for_orchestrator(cached),
                    memory_updates={},
                )
                await self._log_complete(run, result, db, output_summary="Served from cache")
                return result

            # ── 4. Execute web search ───────────────────────────────────────────
            raw_results = await self._execute_web_search(search_query, context.current_message)

            if not raw_results:
                result = AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="web_research",
                    content={"findings": [], "no_results": True},
                    confidence=0.0,
                    priority=7,
                    text_for_orchestrator=(
                        "Mình không tìm thấy thông tin cụ thể về chủ đề này. "
                        "Bạn có thể hỏi cụ thể hơn không?"
                    ),
                    memory_updates={},
                )
                await self._log_complete(run, result, db, output_summary="No results found")
                return result

            # ── 5. Filter to trusted sources ────────────────────────────────────
            filtered = self._filter_trusted_sources(raw_results)

            if not filtered:
                result = AgentResult(
                    agent_name=self.name,
                    success=True,
                    insight_type="web_research",
                    content={"findings": [], "no_trusted_results": True},
                    confidence=0.1,
                    priority=7,
                    text_for_orchestrator=(
                        "Không tìm thấy kết quả từ các nguồn đáng tin cậy. "
                        "Mình khuyên bạn nên tham khảo ý kiến bác sĩ."
                    ),
                    memory_updates={},
                )
                await self._log_complete(run, result, db, output_summary="No trusted sources found")
                return result

            # ── 6. Build structured output ──────────────────────────────────────
            research_output = {
                "findings": filtered[:3],  # max 3 sources
                "search_query_used": search_query,
                "search_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }

            # ── 7. Cache result ────────────────────────────────────────────────
            await cache_set(cache_key, research_output, _WEB_RESEARCH_TTL_SECONDS)

            result = AgentResult(
                agent_name=self.name,
                success=True,
                insight_type="web_research",
                content=research_output,
                confidence=0.75,
                priority=6,
                text_for_orchestrator=self._build_text_for_orchestrator(research_output),
                memory_updates={},
            )
            await self._log_complete(run, result, db, output_summary=search_query)
            return result

        except Exception as exc:
            logger.error("WebResearcherAgent: unexpected error: %s", exc, exc_info=True)
            await self._log_complete(run, AgentResult(
                agent_name=self.name,
                success=False,
                insight_type="web_research",
                content={},
                confidence=0.0,
                priority=5,
                memory_updates={},
                error=str(exc),
            ), db)
            return AgentResult(
                agent_name=self.name,
                success=False,
                insight_type="web_research",
                content={},
                confidence=0.0,
                priority=5,
                memory_updates={},
                error=str(exc),
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _generate_search_query(self, user_message: str) -> str:
        """Use AI to distill user question into an optimal web search query."""
        try:
            raw = await self._call_ai(
                system_prompt=RESEARCHER_SYSTEM_PROMPT,
                user_prompt=f"Câu hỏi: {user_message}\n\nTruy vấn tìm kiếm tối ưu (chỉ 1 dòng, không giải thích):",
                response_format="text",
                max_tokens=80,
                model=settings.GROQ_TEXT_MODEL,
            )
            return str(raw).strip()
        except Exception as exc:
            logger.warning("WebResearcherAgent: query generation failed: %s", exc)
            # Fallback: strip common words and return remaining keywords
            stopwords = {
                "bạn", "của", "có", "không", "là", "mình", "với", "và",
                "tôi", "cho", "được", "hay", "thì", "nên", "hay", "muốn",
            }
            words = user_message.lower().split()
            keywords = [w for w in words if w not in stopwords and len(w) > 3]
            return " ".join(keywords[:8])

    # ── Real web search via Tavily ───────────────────────────────────────────────

    async def _fetch_real_results(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict] | None:
        """
        Call Tavily API to get real web search results.
        Returns None if Tavily is not available (falls back to AI synthesis).
        """
        if not settings.TAVILY_API_KEY or not settings.TAVILY_ENABLED:
            logger.warning("[WebResearcher] Tavily not configured — "
                          "falling back to AI synthesis mode")
            return None

        try:
            client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
            response = await asyncio.wait_for(
                client.search(
                    query=query,
                    max_results=max_results,
                    search_depth="advanced",
                    include_domains=TRUSTED_DOMAINS,
                ),
                timeout=10.0,
            )
            results = response.get("results", [])
            if not results:
                return []

            normalized = []
            for r in results:
                normalized.append({
                    "source_url":     r.get("url", ""),
                    "source_name":    r.get("title", ""),
                    "snippet":        r.get("content", ""),
                    "score":          r.get("score", 0.0),
                    "published_date": r.get("published_date"),
                    "is_real_source": True,
                })
            return normalized

        except asyncio.TimeoutError:
            logger.warning("[WebResearcher] Tavily timeout — fallback to AI synthesis")
            return None
        except Exception as e:
            logger.error(f"[WebResearcher] Tavily error: {e} — fallback to AI synthesis")
            return None

    async def _summarize_real_results(
        self,
        query: str,
        original_question: str,
        real_results: list[dict],
    ) -> list[dict[str, Any]]:
        """
        Use AI to summarize REAL content from Tavily.
        AI must only summarize existing content — not hallucinate claims or URLs.
        """
        content_blocks = []
        for i, r in enumerate(real_results[:5]):
            content_blocks.append(
                f"[Source {i+1}]\n"
                f"URL: {r['source_url']}\n"
                f"Title: {r['source_name']}\n"
                f"Content: {r['snippet'][:500]}\n"
            )
        content_text = "\n---\n".join(content_blocks)

        system_prompt = (
            "Bạn là trợ lý tóm tắt nghiên cứu y khoa. "
            "Nhiệm vụ: tóm tắt các đoạn text thực từ web search, "
            "KHÔNG thêm thông tin nào ngoài nội dung được cung cấp. "
            "KHÔNG tự tạo URLs. KHÔNG tự tạo claims. "
            "Chỉ tóm tắt và trích dẫn từ content được cho. "
            "Trả lời bằng JSON theo schema."
        )
        user_prompt = (
            f"Câu hỏi: {original_question}\n\n"
            f"Nội dung thực từ web search:\n{content_text}\n\n"
            f"Tóm tắt theo schema:\n{FINDINGS_SCHEMA}\n\n"
            "QUAN TRỌNG: Chỉ dùng thông tin từ các đoạn text trên. "
            "Giữ nguyên URLs đã cho. Không thêm URLs mới."
        )

        response_text = await self._call_ai_raw(system_prompt, user_prompt)
        findings = self._parse_findings_json(response_text)

        for f in findings:
            f["is_real_source"] = True
            f["source_verified"] = True

        return findings

    async def _ai_synthesis_fallback(
        self,
        query: str,
        original_question: str,
    ) -> list[dict[str, Any]]:
        """
        Fallback when Tavily is not available.
        AI synthesis with explicit disclaimer — does NOT pretend to be web search.
        """
        system_prompt = (
            "Bạn là trợ lý tóm tắt kiến thức y khoa từ training data. "
            "Hãy cung cấp thông tin tổng quát về câu hỏi. "
            "QUAN TRỌNG: Không bịa đặt URLs cụ thể. "
            "Không tự tạo article IDs. "
            "Chỉ suggest domain nguồn (ví dụ: who.int) không phải URL đầy đủ. "
            "Trả lời bằng JSON theo schema."
        )
        user_prompt = (
            f"Câu hỏi: {original_question}\n\n"
            f"Cung cấp thông tin tổng quát theo schema:\n{FINDINGS_SCHEMA}\n\n"
            "Ghi rõ trong source_url chỉ là domain, VD: 'https://who.int' "
            "(không phải URL bài cụ thể). "
            "Đây là tổng hợp từ kiến thức AI, không phải web search thực."
        )

        response_text = await self._call_ai_raw(system_prompt, user_prompt)
        findings = self._parse_findings_json(response_text)

        for f in findings:
            f["is_real_source"] = False
            f["source_verified"] = False
            f["ai_synthesis_disclaimer"] = (
                "Thông tin này được tổng hợp từ kiến thức AI, "
                "không phải từ web search thực. Vui lòng verify "
                "trực tiếp từ nguồn trước khi áp dụng."
            )

        return findings

    async def _call_ai_raw(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        """Call Groq directly (async) and return raw text response."""
        import time
        start = time.perf_counter()

        client = self._get_groq_client()

        async def _do_call():
            return await client.chat.completions.create(
                model=settings.GROQ_TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

        response = await asyncio.wait_for(
            groq_circuit.call(_do_call),
            timeout=30.0,
        )

        self._last_usage = {
            "input_tokens":  response.usage.prompt_tokens if response.usage else None,
            "output_tokens": response.usage.completion_tokens if response.usage else None,
            "latency_ms":    int((time.perf_counter() - start) * 1000),
            "model":         settings.GROQ_TEXT_MODEL,
        }

        return response.choices[0].message.content or ""

    def _get_groq_client(self):
        from app.agents.base import _get_groq_client
        return _get_groq_client()

    def _parse_findings_json(self, raw_text: str) -> list[dict[str, Any]]:
        """Parse AI JSON response into findings list.

        Robust against the model prefixing the JSON with prose like
        ``"Dưới đây là thông tin tổng quát:"`` and against a markdown
        fence (`` ```json `` ... `` ``` ``) wrapping the payload.
        """
        import re

        if not raw_text:
            return []

        # Find the JSON object/array — prefer fenced ```...```, fall back to
        # the first balanced { ... } or [ ... ] block in the text.
        text = raw_text.strip()

        fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if fence_match:
            candidate = fence_match.group(1)
        else:
            # No fence — extract from first { or [ to matching close.
            first_brace = text.find("{")
            first_bracket = text.find("[")
            candidates_idx = [i for i in (first_brace, first_bracket) if i != -1]
            if not candidates_idx:
                logger.warning("[WebResearcher] No JSON found in response: %s", text[:200])
                return []
            start = min(candidates_idx)
            candidate = text[start:]

        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("[WebResearcher] Failed to parse findings JSON: %s — err=%s",
                           raw_text[:200], e)
            return []

        findings = data.get("findings") or []
        if findings:
            for f in findings:
                f["search_summary"] = data.get("search_summary", "")
                f["overall_confidence"] = data.get("confidence", 0.5)
            return findings
        return []

    async def _execute_web_search(
        self,
        query: str,
        original_question: str,
    ) -> list[dict[str, Any]]:
        """
        Execute web search with real-first strategy:
        1. Tavily real search → AI summarize real content
        2. Fallback: AI synthesis with explicit disclaimer
        """
        # ── Attempt real search ─────────────────────────────────────────
        real_results = await self._fetch_real_results(query)

        if real_results is not None:
            if not real_results:
                return []

            return await self._summarize_real_results(
                query=query,
                original_question=original_question,
                real_results=real_results,
            )
        else:
            # Tavily unavailable — AI synthesis with disclaimer
            logger.warning("[WebResearcher] Using AI synthesis fallback — "
                         "results will be labeled as AI-generated")
            return await self._ai_synthesis_fallback(
                query=query,
                original_question=original_question,
            )

    def _filter_trusted_sources(
        self,
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter and enrich findings to only include trusted sources."""
        filtered = []
        for finding in findings:
            url = finding.get("source_url", "")
            is_trusted, source_key = _source_is_trusted(url)

            if not is_trusted:
                continue

            # Enrich with source quality metadata
            quality = SOURCE_QUALITY.get(source_key, {})
            domain = _extract_domain(url)

            enriched = {
                "source_name": finding.get("source_name") or quality.get("label", domain),
                "source_url": url,
                "source_domain": domain,
                "source_type": quality.get("type", "unknown"),
                "source_tier": quality.get("tier", 3),
                "key_finding": sanitize_for_prompt(finding.get("key_finding", ""), max_length=300),
                "relevance_score": float(finding.get("relevance_score", 0.5)),
                "date_published": finding.get("date_published"),
                "search_summary": finding.get("search_summary", ""),
                "overall_confidence": float(finding.get("overall_confidence", 0.5)),
            }
            filtered.append(enriched)

        # Sort by tier (lower = better), then by relevance
        filtered.sort(key=lambda f: (f["source_tier"], -f["relevance_score"]))
        return filtered

    def _build_text_for_orchestrator(self, content: dict[str, Any]) -> str:
        """Build a natural-language summary from research findings for the orchestrator."""
        findings = content.get("findings") or []
        if not findings:
            return ""

        parts = []
        for f in findings[:3]:
            source = f.get("source_name", "Nguồn")
            finding = f.get("key_finding", "")
            if finding:
                parts.append(f"[{source}] {finding}")

        if not parts:
            return ""

        summary = "\n".join(parts)
        return f"Ket qua nghien cuu web:\n{summary}"
