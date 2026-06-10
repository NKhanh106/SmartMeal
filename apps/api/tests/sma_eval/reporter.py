"""
SMA-Eval v1 — Reporter Engine

Chịu trách nhiệm:
  1. Tính toán CHAS v2 (Composite Health & Agent Score)
  2. Tổng hợp điểm từ nhiều BenchmarkReport (ablation comparison)
  3. Xuất báo cáo: tests/sma_eval/REPORT.md + tests/sma_eval/dashboard.html

CHAS v2 Formula (Balanced System)
──────────────────────────────────
CHAS = (Safety_Score * 0.40) + (Quality_Score * 0.35) + (Performance_Score * 0.25)

  Safety_Score    = avg(AllergenViolation, NutritionalConstraintViolation)
                     (NUTRITION_SAFETY group, weight 0.40)

  Quality_Score   = avg(NutritionalEstimationError, InterAgentConsistency,
                       RecipeFeasibility)
                     (DOMAIN_QUALITY group, weight 0.35)

  Performance_Score = f(latency_ms, token_cost, pool_survival_rate)
                     (MULTI_AGENT_PERFORMANCE group, weight 0.25)

Sử dụng Standalone
──────────────────
  from tests.sma_eval.reporter import CHASv2Calculator, generate_reports

  # Load reports from runner JSON output files
  calc = CHASv2Calculator()
  calc.load_from_json("baseline_results.json")
  calc.load_from_json("partial_results.json")
  calc.load_from_json("full_results.json")

  generate_reports(
      reports={"baseline": calc.get_report("baseline"), ...},
      output_md="REPORT.md",
      output_html="dashboard.html",
  )
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ── path setup ──────────────────────────────────────────────────────────────────
import sys as _sys
_ROOT = Path(__file__).resolve().parents[1]
sys = _sys.path.insert(0, str(_ROOT)); del sys


# ══════════════════════════════════════════════════════════════════════════════
# schemas
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MetricScore:
    """Một metric đơn lẻ."""
    name: str
    score: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return 0.0 <= self.score <= 1.0


@dataclass
class GroupScore:
    """Điểm trung bình của một nhóm metric."""
    name: str
    weight: float
    scores: list[MetricScore]
    avg_score: float
    pass_rate: float  # % metrics passed (>= 0.8)

    @classmethod
    def from_metric_list(
        cls, name: str, weight: float, metrics: list[MetricScore],
    ) -> "GroupScore":
        if not metrics:
            return cls(name=name, weight=weight, scores=[], avg_score=1.0, pass_rate=1.0)
        avg = sum(m.score for m in metrics) / len(metrics)
        passed = sum(1 for m in metrics if m.passed)
        return cls(
            name=name, weight=weight, scores=metrics,
            avg_score=round(avg, 4),
            pass_rate=round(passed / len(metrics), 4),
        )


@dataclass
class PerformanceScore:
    """
    Performance_Score components.

    Được tính từ:
      - Latency: p95 response time (ms) — lower is better
      - Token Cost: total tokens consumed
      - Pool Survival Rate: % requests không bị InfraBreakdownError
    """
    latency_avg_ms: float
    latency_p95_ms: float
    token_cost_total: int
    pool_survival_rate: float   # 0.0 – 1.0
    throughput_rps: float        # requests per second

    def to_score(self) -> float:
        """
        Chuyển đổi 4 metrics thành 1 Performance_Score ∈ [0.0, 1.0].

        Cách tính:
          latency_score = clamp(1 - (p95_ms / 10000), 0, 1)
                       → 1.0 nếu p95 ≤ 100ms, 0.0 nếu p95 ≥ 10000ms

          pool_score   = pool_survival_rate
                       → 1.0 nếu 100% survive, 0.0 nếu 0%

          throughput_score = clamp(rps / 10, 0, 1)
                           → 1.0 nếu ≥ 10 rps, 0.0 nếu 0 rps

          token_score  = clamp(1 - (token_cost / max_expected_tokens), 0, 1)
                        → 1.0 nếu 0 tokens, giảm dần khi token tăng
                        → max_expected_tokens = 500_000 (ước lượng cho full suite)

          Performance_Score = 0.45 * latency + 0.25 * pool + 0.20 * token + 0.10 * throughput
        """
        latency_score = max(0.0, min(1.0, 1.0 - (self.latency_p95_ms / 10_000.0)))
        pool_score   = self.pool_survival_rate
        rps_score    = max(0.0, min(1.0, self.throughput_rps / 10.0))
        max_expected_tokens = 500_000
        token_score  = max(0.0, min(1.0, 1.0 - (self.token_cost_total / max_expected_tokens)))
        return round(
            0.45 * latency_score
            + 0.25 * pool_score
            + 0.20 * token_score
            + 0.10 * rps_score,
            4,
        )


@dataclass
class CHASv2Result:
    """Kết quả CHAS v2 đầy đủ cho một cấu hình."""
    config_name: str
    safety_score: float      # raw group average
    quality_score: float    # raw group average
    performance_score: float # derived
    chas: float             # weighted composite
    safety_details: GroupScore
    quality_details: GroupScore
    performance_details: PerformanceScore
    infra_breakdowns: int
    total_tests: int
    pass_rate: float
    duration_s: float
    tier_breakdown: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "safety_score": round(self.safety_score, 4),
            "quality_score": round(self.quality_score, 4),
            "performance_score": round(self.performance_score, 4),
            "chas": round(self.chas, 4),
            "pass_rate": round(self.pass_rate, 4),
            "infra_breakdowns": self.infra_breakdowns,
            "total_tests": self.total_tests,
            "duration_s": round(self.duration_s, 2),
            "tier_breakdown": self.tier_breakdown,
        }


@dataclass
class AblationComparison:
    """So sánh giữa nhiều cấu hình ablation."""
    configs: dict[str, CHASv2Result]  # config_name → CHASv2Result
    delta_table: dict[str, dict[str, float]]  # delta[cfg1][cfg2] = chas_diff
    winner: str | None

    def chas_delta(self, cfg_a: str, cfg_b: str) -> float:
        """CHAS(cfg_a) - CHAS(cfg_b). Positive = cfg_a better."""
        a = self.configs.get(cfg_a)
        b = self.configs.get(cfg_b)
        if a is None or b is None:
            return 0.0
        return round(a.chas - b.chas, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "configs": {k: v.to_dict() for k, v in self.configs.items()},
            "delta_table": self.delta_table,
            "winner": self.winner,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CHAS v2 calculator
# ══════════════════════════════════════════════════════════════════════════════

class CHASv2Calculator:
    """
    Tính toán CHAS v2 từ BenchmarkReport JSON.

    Usage:
        calc = CHASv2Calculator()
        calc.load_from_json("full_results.json")
        calc.load_from_json("baseline_results.json")
        calc.load_from_json("partial_results.json")

        comparison = calc.compute_comparison()
        calc.generate_reports(comparison, "REPORT.md", "dashboard.html")
    """

    WEIGHTS = {
        "NUTRITION_SAFETY": 0.40,
        "DOMAIN_QUALITY": 0.35,
        "MULTI_AGENT_PERFORMANCE": 0.25,
    }

    # Group → metric name mapping (trùng với metrics.py)
    SAFETY_METRICS = [
        "AllergenViolationMetric",
        "NutritionalConstraintViolationMetric",
    ]
    QUALITY_METRICS = [
        "NutritionalEstimationErrorMetric",
        "InterAgentConsistencyMetric",
        "RecipeFeasibilityMetric",
    ]
    PERFORMANCE_METRICS = [
        "AgentRoleAdherenceMetric",
        "TaskDecompositionQualityMetric",
    ]

    def __init__(self):
        self._reports: dict[str, dict[str, Any]] = {}  # config_name → raw report

    # ── loaders ────────────────────────────────────────────────────────────────

    def load_from_json(self, path: str | Path) -> None:
        """Load một BenchmarkReport từ file JSON của runner."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Report file not found: {p}")
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        config_name = raw.get("config", raw.get("ablation", {}).get("config", p.stem))
        self._reports[config_name] = raw

    def load_from_dict(self, config_name: str, data: dict[str, Any]) -> None:
        """Load một BenchmarkReport trực tiếp từ dict."""
        self._reports[config_name] = data

    def get_report(self, config_name: str) -> CHASv2Result | None:
        """Tính CHAS v2 cho một cấu hình đã load."""
        raw = self._reports.get(config_name)
        if not raw:
            return None
        return self._compute_chas(config_name, raw)

    # ── core computation ──────────────────────────────────────────────────────

    def _extract_metric_scores(
        self, results: list[dict[str, Any]], metric_names: list[str]
    ) -> list[MetricScore]:
        """Gom điểm của các metric cụ thể từ danh sách test results."""
        scores: list[MetricScore] = []

        # Tổng hợp metrics từ 3 tier groups trong mỗi result
        for result in results:
            # nutrition_safety_metrics
            for ns in result.get("nutrition_safety_metrics", []):
                name = ns.get("name", "")
                if name in metric_names:
                    scores.append(MetricScore(
                        name=name,
                        score=float(ns.get("score", 0.0)),
                        passed=bool(ns.get("passed", False)),
                        details=ns,
                    ))

            # domain_quality_metrics
            for dq in result.get("domain_quality_metrics", []):
                name = dq.get("name", "")
                if name in metric_names:
                    scores.append(MetricScore(
                        name=name,
                        score=float(dq.get("score", 0.0)),
                        passed=bool(dq.get("passed", False)),
                        details=dq,
                    ))

            # multi_agent_metrics
            for ma in result.get("multi_agent_metrics", []):
                name = ma.get("name", "")
                if name in metric_names:
                    scores.append(MetricScore(
                        name=name,
                        score=float(ma.get("score", 0.0)),
                        passed=bool(ma.get("passed", False)),
                        details=ma,
                    ))

        # Trong trường hợp metrics chưa được populate (chạy runner cũ),
        # fallback về tier_scores
        if not scores:
            for result in results:
                ts = result.get("tier_scores", {})
                for metric_name in metric_names:
                    # Map metric name → tier_score key
                    tier_map = {
                        "AllergenViolationMetric": "NUTRITION_SAFETY",
                        "NutritionalConstraintViolationMetric": "NUTRITION_SAFETY",
                        "NutritionalEstimationErrorMetric": "DOMAIN_QUALITY",
                        "InterAgentConsistencyMetric": "DOMAIN_QUALITY",
                        "RecipeFeasibilityMetric": "DOMAIN_QUALITY",
                        "AgentRoleAdherenceMetric": "MULTI_AGENT_PERFORMANCE",
                        "TaskDecompositionQualityMetric": "MULTI_AGENT_PERFORMANCE",
                    }
                    tier_key = tier_map.get(metric_name)
                    if tier_key and tier_key in ts:
                        scores.append(MetricScore(
                            name=metric_name,
                            score=float(ts[tier_key]),
                            passed=ts[tier_key] >= 0.8,
                            details={},
                        ))

        return scores

    def _compute_performance_details(
        self, results: list[dict[str, Any]], raw: dict[str, Any]
    ) -> PerformanceScore:
        """
        Tính Performance_Score từ latency, token cost, và pool survival.

        Latency: tính từ duration_ms trong mỗi test result.
        Pool Survival: 1.0 - (infra_breakdowns / total_tests)
        Token Cost: sum của tất cả token từ agent results (ước lượng từ model usage).
        """
        durations = [r.get("duration_ms", 0) for r in results if r.get("duration_ms")]
        latency_avg = sum(durations) / len(durations) if durations else 0.0

        # p95 latency
        if durations:
            sorted_d = sorted(durations)
            p95_idx = int(math.ceil(0.95 * len(sorted_d))) - 1
            p95_latency = sorted_d[max(0, p95_idx)]
        else:
            p95_latency = 0.0

        # Pool survival rate
        summary = raw.get("summary", {})
        total_tests = summary.get("total", len(results))
        infra_bd = summary.get("infra_breakdown", 0)
        pool_survival = max(0.0, 1.0 - (infra_bd / max(total_tests, 1)))

        # Throughput: total_tests / duration_seconds
        duration_s = raw.get("duration_seconds", 1.0)
        throughput_rps = total_tests / max(duration_s, 0.001)

        # Token cost: estimate from agent runs (Groq usage in agent_results_summary)
        # Fallback: 0 if not available
        token_cost = 0
        for r in results:
            agent_summary = r.get("agent_results_summary", {}) or {}
            tokens = agent_summary.get("total_tokens", 0)
            if isinstance(tokens, (int, float)):
                token_cost += int(tokens)

        return PerformanceScore(
            latency_avg_ms=round(latency_avg, 2),
            latency_p95_ms=round(p95_latency, 2),
            token_cost_total=token_cost,
            pool_survival_rate=round(pool_survival, 4),
            throughput_rps=round(throughput_rps, 4),
        )

    def _compute_chas(
        self, config_name: str, raw: dict[str, Any]
    ) -> CHASv2Result:
        results = raw.get("results", [])

        # ── Safety Score ──────────────────────────────────────────────────────
        safety_metrics = self._extract_metric_scores(results, self.SAFETY_METRICS)
        safety_group = GroupScore.from_metric_list(
            "NUTRITION_SAFETY", self.WEIGHTS["NUTRITION_SAFETY"], safety_metrics
        )

        # ── Quality Score ───────────────────────────────────────────────────
        quality_metrics = self._extract_metric_scores(results, self.QUALITY_METRICS)
        quality_group = GroupScore.from_metric_list(
            "DOMAIN_QUALITY", self.WEIGHTS["DOMAIN_QUALITY"], quality_metrics
        )

        # ── Performance Score ───────────────────────────────────────────────
        perf_details = self._compute_performance_details(results, raw)
        perf_score = perf_details.to_score()

        # ── CHAS v2 ────────────────────────────────────────────────────────
        chas = (
            safety_group.avg_score * self.WEIGHTS["NUTRITION_SAFETY"]
            + quality_group.avg_score * self.WEIGHTS["DOMAIN_QUALITY"]
            + perf_score * self.WEIGHTS["MULTI_AGENT_PERFORMANCE"]
        )

        # ── Summary ────────────────────────────────────────────────────────
        summary = raw.get("summary", {})
        tier_breakdown = raw.get("tier_breakdown", {})

        return CHASv2Result(
            config_name=config_name,
            safety_score=safety_group.avg_score,
            quality_score=quality_group.avg_score,
            performance_score=perf_score,
            chas=round(chas, 4),
            safety_details=safety_group,
            quality_details=quality_group,
            performance_details=perf_details,
            infra_breakdowns=summary.get("infra_breakdown", 0),
            total_tests=summary.get("total", len(results)),
            pass_rate=summary.get("pass_rate", 0.0),
            duration_s=raw.get("duration_seconds", 0.0),
            tier_breakdown=tier_breakdown,
        )

    def compute_comparison(self) -> AblationComparison:
        """
        Tính toàn bộ CHAS v2 và so sánh giữa các cấu hình đã load.

        Delta table: delta[cfg_a][cfg_b] = CHAS(cfg_a) - CHAS(cfg_b)
        Positive = cfg_a better than cfg_b.
        """
        configs: dict[str, CHASv2Result] = {}
        for name, raw in self._reports.items():
            result = self._compute_chas(name, raw)
            configs[name] = result

        # Delta table
        delta_table: dict[str, dict[str, float]] = {}
        names = list(configs.keys())
        for a in names:
            delta_table[a] = {}
            for b in names:
                delta_table[a][b] = round(
                    configs[a].chas - configs[b].chas, 4
                )

        # Winner: config có CHAS cao nhất
        winner = max(configs, key=lambda k: configs[k].chas) if configs else None

        return AblationComparison(
            configs=configs,
            delta_table=delta_table,
            winner=winner,
        )

    # ── report generation ────────────────────────────────────────────────────

    def generate_reports(
        self,
        comparison: AblationComparison | None = None,
        output_md: str | Path | None = None,
        output_html: str | Path | None = None,
        title: str = "SMA-Eval v1 — Benchmark Report",
    ) -> dict[str, Path]:
        """
        Sinh cả hai báo cáo (Markdown + HTML) từ comparison data.

        Trả về dict với các đường dẫn file đã ghi.
        """
        if comparison is None:
            comparison = self.compute_comparison()

        outputs: dict[str, Path] = {}

        if output_md:
            md_path = Path(output_md)
            md_path.write_text(
                self._build_markdown(comparison, title),
                encoding="utf-8",
            )
            outputs["markdown"] = md_path
            print(f"[Reporter] Markdown written: {md_path}")

        if output_html:
            html_path = Path(output_html)
            html_path.write_text(
                self._build_html(comparison, title),
                encoding="utf-8",
            )
            outputs["html"] = html_path
            print(f"[Reporter] HTML dashboard written: {html_path}")

        return outputs

    # ══════════════════════════════════════════════════════════════════════════
    # Markdown builder
    # ══════════════════════════════════════════════════════════════════════════

    def _build_markdown(
        self, comparison: AblationComparison, title: str
    ) -> str:
        lines: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        lines.extend([
            f"# {title}",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC+7')}",
            f"**Framework:** SMA-Eval v1",
            "",
            "---",
            "",
        ])

        # ── CHAS v2 Formula ───────────────────────────────────────────────
        lines.extend([
            "## CHAS v2 — Composite Health & Agent Score",
            "",
            "| Metric Group       | Weight | Description                              |",
            "|--------------------|--------|------------------------------------------|",
            "| NUTRITION_SAFETY  | 0.40   | Allergen + Nutritional Constraint Safety   |",
            "| DOMAIN_QUALITY     | 0.35   | MAE + Inter-Agent Consistency + Feasibility |",
            "| MULTI_AGENT_PERFORMANCE | 0.25 | Latency + Pool Survival + Throughput  |",
            "",
            "```",
            "CHAS = (Safety_Score × 0.40)",
            "     + (Quality_Score × 0.35)",
            "     + (Performance_Score × 0.25)",
            "```",
            "",
        ])

        # ── Summary table ─────────────────────────────────────────────────
        lines.extend([
            "## Ablation Study Summary",
            "",
            "| Config     | CHAS v2 | Safety | Quality | Perf. | Pass Rate | Infra BD | Winner? |",
            "|-----------|---------|--------|---------|-------|-----------|----------|---------|",
        ])
        configs = comparison.configs
        for name, result in configs.items():
            winner_mark = "**YES**" if name == comparison.winner else ""
            lines.append(
                f"| {self._fmt_cfg(name)} | "
                f"**{result.chas:.4f}** | "
                f"{result.safety_score:.4f} | "
                f"{result.quality_score:.4f} | "
                f"{result.performance_score:.4f} | "
                f"{result.pass_rate*100:.1f}% | "
                f"{result.infra_breakdowns} | "
                f"{winner_mark} |"
            )
        lines.append("")

        # ── Delta comparison table ────────────────────────────────────────
        if len(configs) >= 2:
            cfg_names = list(configs.keys())
            lines.extend([
                "## Delta Table — CHAS Difference (Row − Column)",
                "",
                "| Config     | " + " | ".join(self._fmt_cfg(c) for c in cfg_names) + " |",
                "|-----------|" + "|".join(["---"] * len(cfg_names)) + "|",
            ])
            for row in cfg_names:
                row_cells = [f"| {self._fmt_cfg(row)} |"]
                for col in cfg_names:
                    delta = comparison.chas_delta(row, col)
                    sign = "+" if delta >= 0 else ""
                    cell = f"{sign}{delta:.4f}"
                    # Highlight winner row
                    if row == comparison.winner:
                        cell = f"**{cell}**"
                    row_cells.append(f" {cell} |")
                lines.append("".join(row_cells))
            lines.append("")

        # ── Tier breakdown ─────────────────────────────────────────────────
        lines.extend([
            "## Tier Breakdown",
            "",
            "| Tier | Config     | Tests | Passed | Score Avg |",
            "|------|-----------|-------|--------|-----------|",
        ])
        for name, result in configs.items():
            tb = result.tier_breakdown
            for tier in ("A", "B", "C"):
                t = tb.get(tier, {})
                if t:
                    score = t.get("score_avg", 0.0)
                    lines.append(
                        f"| {tier} | {self._fmt_cfg(name)} "
                        f"| {t.get('total', 0)} "
                        f"| {t.get('passed', 0)} "
                        f"| {score:.4f} |"
                    )
        lines.append("")

        # ── Performance details ───────────────────────────────────────────
        lines.extend([
            "## Performance Details",
            "",
            "| Config     | Avg Latency (ms) | P95 Latency (ms) | Pool Survival | Throughput (rps) |",
            "|-----------|-----------------|------------------|---------------|-------------------|",
        ])
        for name, result in configs.items():
            pd = result.performance_details
            lines.append(
                f"| {self._fmt_cfg(name)} "
                f"| {pd.latency_avg_ms:.1f} "
                f"| {pd.latency_p95_ms:.1f} "
                f"| {pd.pool_survival_rate*100:.1f}% "
                f"| {pd.throughput_rps:.2f} |"
            )
        lines.append("")

        # ── Metric-level detail ───────────────────────────────────────────
        lines.extend([
            "## Metric Scores Detail",
            "",
        ])
        for group_name, group_attr, weight in [
            ("NUTRITION_SAFETY", "safety_details", 0.40),
            ("DOMAIN_QUALITY", "quality_details", 0.35),
            ("MULTI_AGENT_PERFORMANCE", "performance_details", 0.25),
        ]:
            lines.extend([f"### {group_name} (weight={weight})", ""])
            lines.append(
                "| Metric | " + " | ".join(self._fmt_cfg(n) for n in configs.keys()) + " |"
            )
            lines.append("|" + "|".join(["---"] * (len(configs) + 1)) + "|")

            # Collect all metric names in this group
            metric_names: list[str] = []
            for result in configs.values():
                group = getattr(result, group_attr, None)
                if group:
                    for m in group.scores:
                        if m.name not in metric_names:
                            metric_names.append(m.name)

            for mn in metric_names:
                row = [f"| {mn}"]
                for result in configs.values():
                    group = getattr(result, group_attr, None)
                    if group:
                        found = next((m for m in group.scores if m.name == mn), None)
                        score = found.score if found else 0.0
                        row.append(f" {score:.4f} |")
                    else:
                        row.append(" — |")
                lines.append("".join(row))
            lines.append("")

        # ── Interpretation ───────────────────────────────────────────────
        lines.extend([
            "## Interpretation Guide",
            "",
            "- **CHAS ≥ 0.85**: Hệ thống xuất sắc, sẵn sàng production.",
            "- **CHAS 0.70–0.85**: Hệ thống tốt, cần cải thiện vài nhóm metric.",
            "- **CHAS 0.50–0.70**: Hệ thống trung bình, cần tối ưu nghiêm túc.",
            "- **CHAS < 0.50**: Hệ thống chưa đạt yêu cầu, nguy hiểm cho production.",
            "",
            f"- **Winner:** `{comparison.winner}` — CHAS cao nhất trong ablation study.",
            "",
            "---",
            f"*SMA-Eval v1 — SmartMeal Multi-Agent Evaluation Framework — {datetime.now().year}*",
        ])

        return "\n".join(lines)

    @staticmethod
    def _fmt_cfg(name: str) -> str:
        """Format config name for display."""
        return {
            "baseline": "**BASELINE**",
            "partial": "PARTIAL",
            "full": "**FULL**",
        }.get(name, name)

    # ══════════════════════════════════════════════════════════════════════════
    # HTML dashboard builder
    # ══════════════════════════════════════════════════════════════════════════

    def _build_html(self, comparison: AblationComparison, title: str) -> str:
        configs = comparison.configs

        # Build score table rows
        config_names = list(configs.keys())
        score_rows = []
        for name in config_names:
            r = configs[name]
            is_winner = name == comparison.winner
            winner_tag = ' class="winner"' if is_winner else ""
            score_rows.append(f"""
            <tr{winner_tag}>
              <td><strong>{name.upper()}</strong></td>
              <td class="{'chas-cell' if is_winner else ''}">{r.chas:.4f}</td>
              <td>{r.safety_score:.4f}</td>
              <td>{r.quality_score:.4f}</td>
              <td>{r.performance_score:.4f}</td>
              <td>{r.pass_rate*100:.1f}%</td>
              <td class="{'infra-ok' if r.infra_breakdowns == 0 else 'infra-err'}">{r.infra_breakdowns}</td>
              <td>{r.total_tests}</td>
              <td>{r.duration_s:.1f}s</td>
              <td>{'YES' if is_winner else '—'}</td>
            </tr>""")

        # Build delta table
        delta_rows = []
        for row in config_names:
            cells = [f"<td><strong>{row.upper()}</strong></td>"]
            for col in config_names:
                delta = comparison.chas_delta(row, col)
                cls = "delta-pos" if delta > 0 else ("delta-neg" if delta < 0 else "delta-zero")
                cells.append(f'<td class="{cls}">{"+" if delta >= 0 else ""}{delta:.4f}</td>')
            delta_rows.append(f"<tr>{''.join(cells)}</tr>")

        # Build tier breakdown
        tier_rows = []
        for name in config_names:
            r = configs[name]
            for tier in ("A", "B", "C"):
                t = r.tier_breakdown.get(tier, {})
                if t:
                    score = t.get("score_avg", 0.0)
                    bar_w = score * 100
                    tier_rows.append(f"""
            <tr>
              <td>{tier}</td>
              <td>{name.upper()}</td>
              <td>{t.get('total', 0)}</td>
              <td>{t.get('passed', 0)}</td>
              <td>
                <div class="score-bar">
                  <div class="score-fill" style="width:{bar_w:.0f}%"></div>
                  <span>{score:.4f}</span>
                </div>
              </td>
            </tr>""")

        # Build performance table
        perf_rows = []
        for name in config_names:
            pd = configs[name].performance_details
            pool_cls = "infra-ok" if pd.pool_survival_rate >= 0.9 else ("infra-warn" if pd.pool_survival_rate >= 0.7 else "infra-err")
            perf_rows.append(f"""
            <tr>
              <td>{name.upper()}</td>
              <td>{pd.latency_avg_ms:.1f}</td>
              <td>{pd.latency_p95_ms:.1f}</td>
              <td class="{pool_cls}">{pd.pool_survival_rate*100:.1f}%</td>
              <td>{pd.throughput_rps:.2f}</td>
              <td>{pd.token_cost_total}</td>
            </tr>""")

        # Winner badge
        winner_badge = ""
        if comparison.winner:
            winner_chas = configs[comparison.winner].chas
            winner_badge = f"""
        <div class="winner-badge">
          <span class="badge-label">CHẠM THẮNG</span>
          <span class="badge-config">{comparison.winner.upper()}</span>
          <span class="badge-score">CHAS v2 = {winner_chas:.4f}</span>
        </div>"""

        # Metric detail table
        metric_rows = []
        for group_name, group_attr in [
            ("NUTRITION_SAFETY", "safety_details"),
            ("DOMAIN_QUALITY", "quality_details"),
            ("MULTI_AGENT_PERFORMANCE", "performance_details"),
        ]:
            metric_rows.append(f'<tr class="group-header"><td colspan="{len(configs)+1}">{group_name}</td></tr>')
            metric_names: list[str] = []
            for result in configs.values():
                group = getattr(result, group_attr, None)
                if group:
                    for m in group.scores:
                        if m.name not in metric_names:
                            metric_names.append(m.name)
            for mn in metric_names:
                cells = [f"<td>{mn}</td>"]
                for result in configs.values():
                    group = getattr(result, group_attr, None)
                    if group:
                        found = next((m for m in group.scores if m.name == mn), None)
                        score = found.score if found else None
                        if score is not None:
                            color = "#d4edda" if score >= 0.8 else ("#fff3cd" if score >= 0.5 else "#f8d7da")
                            cells.append(f'<td style="background:{color}">{score:.4f}</td>')
                        else:
                            cells.append("<td>—</td>")
                    else:
                        cells.append("<td>—</td>")
                metric_rows.append(f"<tr>{''.join(cells)}</tr>")

        # Radar chart data
        radar_labels = ["Safety", "Quality", "Performance", "CHAS"]
        radar_datasets = []
        colors = ["#0d6efd", "#198754", "#dc3545", "#ffc107"]
        for i, (name, r) in enumerate(configs.items()):
            safety = r.safety_score
            quality = r.quality_score
            performance = r.performance_score
            chas = r.chas
            radar_datasets.append(f"""{{
              label: "{name.upper()}",
              data: [{safety}, {quality}, {performance}, {chas}],
              borderColor: "{colors[i % len(colors)]}",
              backgroundColor: "{colors[i % len(colors)]}20",
              borderWidth: 2,
              tension: 0.3,
            }}""")

        return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg: #0f172a;
      --surface: #1e293b;
      --surface2: #334155;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --border: #475569;
      --accent: #38bdf8;
      --success: #4ade80;
      --warning: #fbbf24;
      --danger: #f87171;
      --win-bg: #064e3b;
      --win-border: #22c55e;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 2rem;
    }}
    .container {{ max-width: 1400px; margin: 0 auto; }}
    .header {{ text-align: center; margin-bottom: 2rem; }}
    .header h1 {{
      font-size: 1.8rem;
      color: var(--accent);
      letter-spacing: 0.05em;
    }}
    .header p {{ color: var(--text-muted); font-size: 0.9rem; }}
    .winner-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.75rem;
      background: var(--win-bg);
      border: 2px solid var(--win-border);
      border-radius: 12px;
      padding: 0.6rem 1.5rem;
      margin-top: 1rem;
    }}
    .badge-label {{ font-size: 0.7rem; letter-spacing: 0.1em; color: var(--win-border); font-weight: 700; }}
    .badge-config {{ font-size: 1.2rem; font-weight: 800; color: var(--success); }}
    .badge-score {{ font-size: 1rem; color: var(--text); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
    }}
    .card h2 {{ font-size: 1rem; color: var(--accent); letter-spacing: 0.05em; margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    th {{
      background: var(--surface2);
      color: var(--text-muted);
      font-weight: 600;
      padding: 0.5rem 0.75rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    td {{
      padding: 0.5rem 0.75rem;
      border-bottom: 1px solid var(--border);
      color: var(--text);
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: var(--surface2); }}
    tr.winner td {{ background: #052e16; font-weight: 600; }}
    tr.winner td:first-child {{ color: var(--success); }}
    .chas-cell {{ color: var(--success); font-size: 1rem; font-weight: 700; }}
    .infra-ok {{ color: var(--success); }}
    .infra-err {{ color: var(--danger); font-weight: 700; }}
    .infra-warn {{ color: var(--warning); }}
    .delta-pos {{ color: var(--success); font-weight: 600; }}
    .delta-neg {{ color: var(--danger); }}
    .delta-zero {{ color: var(--text-muted); }}
    tr.group-header td {{ background: var(--surface2); color: var(--accent); font-weight: 700; letter-spacing: 0.05em; }}
    .score-bar {{ position: relative; height: 20px; background: var(--surface2); border-radius: 4px; overflow: hidden; }}
    .score-bar .score-fill {{ height: 100%; background: var(--success); border-radius: 4px; }}
    .score-bar span {{ position: absolute; inset: 0; display: flex; align-items: center; padding-left: 0.5rem; font-size: 0.75rem; color: var(--bg); font-weight: 600; }}
    .chart-container {{ position: relative; height: 320px; }}
    .formula-box {{
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem 1.5rem;
      font-family: 'Consolas', monospace;
      font-size: 0.95rem;
      color: var(--accent);
      text-align: center;
      margin-bottom: 1rem;
    }}
    .pass-rate-bar {{ height: 8px; background: var(--surface2); border-radius: 4px; overflow: hidden; margin-top: 4px; }}
    .pass-rate-fill {{ height: 100%; background: var(--success); border-radius: 4px; }}
    .footer {{ text-align: center; color: var(--text-muted); font-size: 0.8rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); }}
  </style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>{title}</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC+7')} &nbsp;|&nbsp; SMA-Eval Framework v1</p>
    {winner_badge}
  </div>

  <!-- CHAS Formula -->
  <div class="card" style="margin-bottom:1.5rem;">
    <h2>CHAS v2 — Composite Health &amp; Agent Score</h2>
    <div class="formula-box">
      CHAS = (Safety_Score &times; 0.40) + (Quality_Score &times; 0.35) + (Performance_Score &times; 0.25)
    </div>
    <table>
      <thead>
        <tr>
          <th>Config</th>
          <th>CHAS v2</th>
          <th>Safety (0.40)</th>
          <th>Quality (0.35)</th>
          <th>Performance (0.25)</th>
          <th>Pass Rate</th>
          <th>Infra BD</th>
          <th>Tests</th>
          <th>Duration</th>
          <th>Winner</th>
        </tr>
      </thead>
      <tbody>
        {"".join(score_rows)}
      </tbody>
    </table>
  </div>

  <div class="grid">
    <!-- Radar Chart -->
    <div class="card">
      <h2>Multi-Dimensional Score Radar</h2>
      <div class="chart-container">
        <canvas id="radarChart"></canvas>
      </div>
    </div>

    <!-- Pass Rate Bar Chart -->
    <div class="card">
      <h2>Pass Rate Comparison</h2>
      <div class="chart-container">
        <canvas id="barChart"></canvas>
      </div>
    </div>
  </div>

  <!-- Delta Table -->
  <div class="card" style="margin-bottom:1.5rem;">
    <h2>Delta Table — CHAS Difference (Row − Column)</h2>
    <table>
      <thead>
        <tr>
          <th>\\ Col</th>
          {"".join(f"<th>{n.upper()}</th>" for n in config_names)}
        </tr>
      </thead>
      <tbody>
        {"".join(delta_rows)}
      </tbody>
    </table>
  </div>

  <div class="grid">
    <!-- Tier Breakdown -->
    <div class="card">
      <h2>Per-Tier Score Breakdown</h2>
      <table>
        <thead>
          <tr>
            <th>Tier</th>
            <th>Config</th>
            <th>Tests</th>
            <th>Passed</th>
            <th>Score Avg</th>
          </tr>
        </thead>
        <tbody>
          {"".join(tier_rows)}
        </tbody>
      </table>
    </div>

    <!-- Performance -->
    <div class="card">
      <h2>Performance Metrics</h2>
      <table>
        <thead>
          <tr>
            <th>Config</th>
            <th>Avg Latency</th>
            <th>P95 Latency</th>
            <th>Pool Survival</th>
            <th>Throughput</th>
            <th>Token Cost</th>
          </tr>
        </thead>
        <tbody>
          {"".join(perf_rows)}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Metric Detail -->
  <div class="card">
    <h2>Metric-Level Score Detail</h2>
    <table>
      <thead>
        <tr>
          <th>Metric</th>
          {"".join(f"<th>{n.upper()}</th>" for n in config_names)}
        </tr>
      </thead>
      <tbody>
        {"".join(metric_rows)}
      </tbody>
    </table>
  </div>

  <!-- Interpretation -->
  <div class="card" style="margin-top:1.5rem;">
    <h2>Interpretation Guide</h2>
    <table>
      <thead><tr><th>CHAS Range</th><th>Rating</th><th>Recommendation</th></tr></thead>
      <tbody>
        <tr style="background:#052e16">
          <td style="color:var(--success);font-weight:700">≥ 0.85</td>
          <td style="color:var(--success)">Excellent</td>
          <td>Hệ thống xuất sắc, sẵn sàng production</td>
        </tr>
        <tr style="background:#1c2b14">
          <td style="color:#86efac">0.70 – 0.85</td>
          <td style="color:#86efac">Good</td>
          <td>Cần cải thiện vài metric groups</td>
        </tr>
        <tr style="background:#2d2008">
          <td style="color:#fde047">0.50 – 0.70</td>
          <td style="color:#fde047">Fair</td>
          <td>Cần tối ưu nghiêm túc trước production</td>
        </tr>
        <tr style="background:#2d0f0f">
          <td style="color:#f87171;font-weight:700">&lt; 0.50</td>
          <td style="color:#f87171">Poor</td>
          <td>Chưa đạt yêu cầu, nguy hiểm cho production</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="footer">
    SMA-Eval v1 — SmartMeal Multi-Agent Evaluation Framework<br>
    Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC+7')}<br>
    SmartMeal Graduation Project 2026
  </div>
</div>

<script>
const radarCtx = document.getElementById('radarChart').getContext('2d');
const radarLabels = {json.dumps(radar_labels)};
const radarDatasets = [{",".join(radar_datasets)}];

new Chart(radarCtx, {{
  type: 'radar',
  data: {{ labels: radarLabels, datasets: radarDatasets }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    scales: {{
      r: {{
        min: 0, max: 1,
        ticks: {{ stepSize: 0.2, color: '#94a3b8', backdropColor: 'transparent' }},
        grid: {{ color: '#334155' }},
        angleLines: {{ color: '#334155' }},
        pointLabels: {{ color: '#f1f5f9', font: {{ size: 12 }} }},
      }}
    }},
    plugins: {{
      legend: {{ position: 'bottom', labels: {{ color: '#f1f5f9', padding: 20 }} }},
    }},
  }},
}});

const barCtx = document.getElementById('barChart').getContext('2d');
const barLabels = {json.dumps([n.upper() for n in config_names])};
const barPassRates = {json.dumps([configs[n].pass_rate * 100 for n in config_names])};
const barChas = {json.dumps([configs[n].chas * 100 for n in config_names])};

new Chart(barCtx, {{
  type: 'bar',
  data: {{
    labels: barLabels,
    datasets: [
      {{
        label: 'Pass Rate (%)',
        data: barPassRates,
        backgroundColor: '#4ade80',
        borderRadius: 4,
      }},
      {{
        label: 'CHAS v2 (×100)',
        data: barChas,
        backgroundColor: '#38bdf8',
        borderRadius: 4,
      }},
    ],
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }},
      y: {{
        min: 0, max: 100,
        ticks: {{ color: '#94a3b8', callback: v => v + '%' }},
        grid: {{ color: '#334155' }},
      }},
    }},
    plugins: {{
      legend: {{ position: 'bottom', labels: {{ color: '#f1f5f9', padding: 20 }} }},
    }},
  }},
}});
</script>
</body>
</html>"""
