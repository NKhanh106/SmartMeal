/**
 * Admin / Agent monitoring API types and service.
 */

import { api } from "@/lib/api-client";

// ─── Agent Stats ───────────────────────────────────────────────────────────────

export interface AgentStatRow {
  agent_name: string;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  skipped_runs: number;
  failure_rate_pct: number;
  avg_latency_ms: number;
  max_latency_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens_formatted: string;
}

export interface TriggerDistribution {
  trigger: string;
  count: number;
  pct: number;
}

export interface RecentFailure {
  run_id: string;
  agent_name: string;
  trigger: string;
  user_id: string;
  error_message: string;
  latency_ms: number | null;
  created_at: string;
}

export interface AgentStatsResponse {
  period_hours: number;
  generated_at: string;
  total_runs: number;
  orchestrator_runs: number;
  agents: AgentStatRow[];
  trigger_distribution: TriggerDistribution[];
  recent_failures: RecentFailure[];
  failure_summary: {
    total: number;
    by_agent: Record<string, number>;
  };
}

export interface AgentRunListItem {
  run_id: string;
  agent_name: string;
  user_id: string;
  session_id: string | null;
  trigger: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  input_summary: string | null;
  output_summary: string | null;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface AgentRunListResponse {
  total: number;
  limit: number;
  offset: number;
  items: AgentRunListItem[];
}

// ─── Service ─────────────────────────────────────────────────────────────────

export const adminAgentsService = {
  async getAgentStats(hours: number = 24): Promise<AgentStatsResponse> {
    return api.get<AgentStatsResponse>(
      `/api/v1/admin/agents/stats?hours=${hours}`
    );
  },

  async getAgentRuns(params: {
    agent_name?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<AgentRunListResponse> {
    const searchParams = new URLSearchParams();
    if (params.agent_name) searchParams.set("agent_name", params.agent_name);
    if (params.status) searchParams.set("status", params.status);
    if (params.limit) searchParams.set("limit", String(params.limit));
    if (params.offset) searchParams.set("offset", String(params.offset));
    return api.get<AgentRunListResponse>(
      `/api/v1/admin/agents/runs?${searchParams.toString()}`
    );
  },

  async getAgentRunDetail(runId: string): Promise<Record<string, unknown>> {
    return api.get<Record<string, unknown>>(`/api/v1/admin/agents/runs/${runId}`);
  },
};

// ─── Formatting helpers ───────────────────────────────────────────────────────

export function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

export function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export const AGENT_DISPLAY_NAMES: Record<string, string> = {
  orchestrator: "Orchestrator",
  extractor: "Extractor",
  health_monitor: "Health Monitor",
  nutrition_advisor: "Nutrition Advisor",
  fitness_coach: "Fitness Coach",
  web_researcher: "Web Researcher",
};

export const AGENT_COLORS: Record<string, string> = {
  orchestrator: "bg-violet-100 text-violet-700",
  extractor: "bg-blue-100 text-blue-700",
  health_monitor: "bg-red-100 text-red-700",
  nutrition_advisor: "bg-green-100 text-green-700",
  fitness_coach: "bg-orange-100 text-orange-700",
  web_researcher: "bg-cyan-100 text-cyan-700",
};

export const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-blue-100 text-blue-700",
  skipped: "bg-gray-100 text-gray-600",
  pending: "bg-gray-100 text-gray-400",
};
