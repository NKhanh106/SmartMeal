"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  BarChart3,
  Bot,
  ChevronDown,
  Clock,
  Download,
  Filter,
  RefreshCw,
  Shield,
  TrendingUp,
  Users,
  X,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/auth-context";
import {
  AGENT_COLORS,
  AGENT_DISPLAY_NAMES,
  adminAgentsService,
  formatLatency,
  formatRelativeTime,
  formatTokens,
  STATUS_COLORS,
  type AgentStatsResponse,
  type AgentStatRow,
  type RecentFailure,
  type TriggerDistribution,
} from "@/services/admin-agents.service";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function FailureRateCell({ rate }: { rate: number }) {
  const color =
    rate > 5 ? "text-red-600" : rate > 2 ? "text-yellow-600" : "text-green-600";
  return <span className={cn("font-mono font-medium", color)}>{rate}%</span>;
}

function LatencyCell({ ms }: { ms: number }) {
  const color = ms > 5000 ? "text-red-600" : ms > 2000 ? "text-yellow-600" : "text-foreground";
  return <span className={cn("font-mono text-sm", color)}>{formatLatency(ms)}</span>;
}

function AgentBadge({ name }: { name: string }) {
  const colorClass = AGENT_COLORS[name] ?? "bg-gray-100 text-gray-700";
  const displayName = AGENT_DISPLAY_NAMES[name] ?? name;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold", colorClass)}>
      {name === "web_researcher" && <Zap className="h-3 w-3" />}
      {name === "health_monitor" && <AlertCircle className="h-3 w-3" />}
      {name === "extractor" && <Bot className="h-3 w-3" />}
      {displayName}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colorClass = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold capitalize", colorClass)}>
      {status}
    </span>
  );
}

function MiniBar({ pct, maxPct = 100 }: { pct: number; maxPct?: number }) {
  const width = Math.min(100, (pct / maxPct) * 100);
  return (
    <div className="h-2 w-24 rounded-full bg-gray-100 overflow-hidden">
      <div
        className="h-full rounded-full bg-primary transition-all duration-500"
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

// ─── Agent Stats Table ────────────────────────────────────────────────────────

function AgentStatsTable({ agents }: { agents: AgentStatRow[] }) {
  return (
    <div className="rounded-lg border overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead className="font-semibold">Agent</TableHead>
            <TableHead className="text-right font-semibold">Runs</TableHead>
            <TableHead className="text-right font-semibold">Avg Latency</TableHead>
            <TableHead className="text-right font-semibold">Max Latency</TableHead>
            <TableHead className="text-right font-semibold">Failures</TableHead>
            <TableHead className="text-right font-semibold">Failure Rate</TableHead>
            <TableHead className="text-right font-semibold">Tokens</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {agents.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                No agent runs in this period.
              </TableCell>
            </TableRow>
          ) : (
            agents.map((agent) => (
              <TableRow key={agent.agent_name} className="hover:bg-muted/30 transition-colors">
                <TableCell>
                  <AgentBadge name={agent.agent_name} />
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {agent.total_runs.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  <LatencyCell ms={agent.avg_latency_ms} />
                </TableCell>
                <TableCell className="text-right text-muted-foreground text-sm">
                  {agent.max_latency_ms > 0 ? formatLatency(agent.max_latency_ms) : "—"}
                </TableCell>
                <TableCell className="text-right">
                  {agent.failed_runs > 0 ? (
                    <span className="font-mono text-sm text-red-600">
                      {agent.failed_runs}
                    </span>
                  ) : (
                    <span className="text-muted-foreground text-sm">0</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <MiniBar pct={agent.failure_rate_pct} maxPct={10} />
                    <FailureRateCell rate={agent.failure_rate_pct} />
                  </div>
                </TableCell>
                <TableCell className="text-right font-mono text-sm text-muted-foreground">
                  {agent.total_tokens_formatted}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}

// ─── Trigger Distribution ─────────────────────────────────────────────────────

function TriggerDistributionChart({ triggers }: { triggers: TriggerDistribution[] }) {
  const maxCount = Math.max(...triggers.map((t) => t.count), 1);
  const AGENT_FOR_TRIGGER: Record<string, string> = {
    post_user_message: "extractor",
    health_keyword_detected: "health_monitor",
    web_research_requested: "web_researcher",
    scheduled: "orchestrator",
    agent_request: "orchestrator",
    user_message: "orchestrator",
  };

  return (
    <div className="space-y-3">
      {triggers.map((t) => (
        <div key={t.trigger} className="flex items-center gap-3">
          <div className="w-44 text-sm truncate font-medium">
            {t.trigger}
          </div>
          <MiniBar pct={(t.count / maxCount) * 100} />
          <div className="w-10 text-right font-mono text-sm text-muted-foreground">
            {t.count}
          </div>
          <div className="w-12 text-right font-mono text-sm text-muted-foreground">
            {t.pct}%
          </div>
          <AgentBadge name={AGENT_FOR_TRIGGER[t.trigger] ?? "orchestrator"} />
        </div>
      ))}
    </div>
  );
}

// ─── Recent Failures ─────────────────────────────────────────────────────────

function RecentFailuresList({ failures }: { failures: RecentFailure[] }) {
  if (failures.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
        <TrendingUp className="h-4 w-4 mr-2" />
        No failures in this period — all agents running smoothly!
      </div>
    );
  }

  return (
    <div className="divide-y">
      {failures.map((f) => (
        <div
          key={f.run_id}
          className="flex items-start gap-3 py-3 px-1 hover:bg-muted/30 rounded"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0 text-red-500" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-muted-foreground font-mono">
                {formatRelativeTime(f.created_at)}
              </span>
              <AgentBadge name={f.agent_name} />
              <StatusBadge status="failed" />
              {f.trigger && (
                <span className="text-xs text-muted-foreground">
                  triggered by: {f.trigger}
                </span>
              )}
            </div>
            {f.error_message && (
              <p className="mt-1 text-xs text-red-600/80 line-clamp-2">
                {f.error_message}
              </p>
            )}
            <p className="mt-0.5 text-xs text-muted-foreground font-mono">
              {f.latency_ms != null ? `${formatLatency(f.latency_ms)}` : "—"} ·{" "}
              {f.user_id.slice(0, 8)}…
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Summary Cards ───────────────────────────────────────────────────────────

function SummaryCards({ stats }: { stats: AgentStatsResponse }) {
  const cards = [
    {
      label: "Total Runs",
      value: stats.total_runs.toLocaleString(),
      icon: Bot,
      color: "text-violet-600",
      bg: "bg-violet-50",
    },
    {
      label: "Avg Latency",
      value: stats.agents.length
        ? formatLatency(
            Math.round(
              stats.agents.reduce((sum, a) => sum + a.avg_latency_ms * a.total_runs, 0) /
                Math.max(stats.total_runs, 1)
            )
          )
        : "—",
      icon: Clock,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      label: "Total Failures",
      value: stats.failure_summary.total,
      icon: AlertCircle,
      color: stats.failure_summary.total > 0 ? "text-red-600" : "text-green-600",
      bg: stats.failure_summary.total > 0 ? "bg-red-50" : "bg-green-50",
    },
    {
      label: "Active Agents",
      value: stats.agents.length,
      icon: Shield,
      color: "text-emerald-600",
      bg: "bg-emerald-50",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {cards.map((c) => (
        <Card key={c.label} className="hover:shadow-sm transition-shadow">
          <CardContent className="flex items-center gap-4 p-4">
            <div className={cn("rounded-xl p-2.5", c.bg)}>
              <c.icon className={cn("h-5 w-5", c.color)} />
            </div>
            <div>
              <p className="text-2xl font-bold">{c.value}</p>
              <p className="text-xs text-muted-foreground">{c.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ─── Period Selector ──────────────────────────────────────────────────────────

const PERIODS = [
  { label: "Last 24h", value: 24 },
  { label: "Last 3 days", value: 72 },
  { label: "Last 7 days", value: 168 },
];

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function AdminAgentsPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<AgentStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState(24);
  const [activeTab, setActiveTab] = useState("overview");
  const [visibleAgents, setVisibleAgents] = useState<Set<string>>(new Set());

  const isAdmin = user?.role === "admin";

  const fetchStats = useCallback(async () => {
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const data = await adminAgentsService.getAgentStats(period);
      setStats(data);
      setVisibleAgents(new Set(data.agents.map((a) => a.agent_name)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agent stats");
    } finally {
      setLoading(false);
    }
  }, [period, isAdmin]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // ── Access denied ────────────────────────────────────────────────────────
  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <Shield className="h-16 w-16 text-muted-foreground/50" />
        <h1 className="text-xl font-bold">Admin Access Required</h1>
        <p className="text-muted-foreground text-center max-w-sm">
          The Agent Performance Dashboard is only accessible to administrators.
        </p>
        <Button variant="outline" onClick={() => (window.location.href = "/dashboard")}>
          Back to Dashboard
        </Button>
      </div>
    );
  }

  // ── Loading ─────────────────────────────────────────────────────────────
  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center py-24 gap-3">
        <RefreshCw className="h-6 w-6 animate-spin text-primary" />
        <span className="text-muted-foreground">Loading agent stats...</span>
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-red-600 font-medium">{error}</p>
        <Button variant="outline" onClick={fetchStats}>
          <RefreshCw className="h-4 w-4 mr-2" /> Retry
        </Button>
      </div>
    );
  }

  if (!stats) return null;

  // ── Filtered agents ────────────────────────────────────────────────────
  const filteredAgents = stats.agents.filter((a) => visibleAgents.has(a.agent_name));

  return (
    <div className="space-y-6">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-7 w-7 text-violet-600" />
            <h1 className="text-2xl font-bold tracking-tight">
              Agent Performance Dashboard
            </h1>
          </div>
          <p className="text-muted-foreground text-sm mt-1">
            Real-time monitoring of all SmartMeal AI agents ·{" "}
            <span className="font-medium">
              Generated {formatRelativeTime(stats.generated_at)}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Period selector */}
          <Select
            value={String(period)}
            onValueChange={(v) => setPeriod(Number(v))}
          >
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p.value} value={String(p.value)}>
                  Last {p.label.replace("Last ", "")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Agent filter */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Filter className="h-4 w-4 mr-2" />
                Filter Agents
                <ChevronDown className="h-4 w-4 ml-2" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {stats.agents.map((agent) => (
                <DropdownMenuCheckboxItem
                  key={agent.agent_name}
                  checked={visibleAgents.has(agent.agent_name)}
                  onCheckedChange={(checked) => {
                    setVisibleAgents((prev) => {
                      const next = new Set(prev);
                      if (checked) next.add(agent.agent_name);
                      else next.delete(agent.agent_name);
                      return next;
                    });
                  }}
                >
                  <AgentBadge name={agent.agent_name} />
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <Button variant="outline" size="sm" onClick={fetchStats}>
            <RefreshCw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── Summary Cards ────────────────────────────────────────────── */}
      <SummaryCards stats={stats} />

      {/* ── Tabs ────────────────────────────────────────────────────── */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3 sm:w-auto sm:grid-cols-3">
          <TabsTrigger value="overview" className="gap-2">
            <BarChart3 className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="triggers" className="gap-2">
            <Zap className="h-4 w-4" />
            Triggers
          </TabsTrigger>
          <TabsTrigger value="failures" className="gap-2">
            <AlertCircle className="h-4 w-4" />
            Failures
            {stats.recent_failures.length > 0 && (
              <span className="ml-1 inline-flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-xs font-bold text-red-600">
                {stats.recent_failures.length}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* ── Overview Tab ──────────────────────────────────────────── */}
        <TabsContent value="overview" className="space-y-4 mt-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Bot className="h-5 w-5 text-violet-600" />
                    Agent Performance — Last {period}h
                  </CardTitle>
                  <CardDescription>
                    {filteredAgents.length} of {stats.agents.length} agents visible
                    {filteredAgents.length !== stats.agents.length && (
                      <button
                        className="ml-2 text-primary underline text-xs"
                        onClick={() =>
                          setVisibleAgents(new Set(stats.agents.map((a) => a.agent_name)))
                        }
                      >
                        Show all
                      </button>
                    )}
                  </CardDescription>
                </div>
                <span className="text-xs text-muted-foreground">
                  {filteredAgents.length} agents
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <AgentStatsTable agents={filteredAgents} />
            </CardContent>
          </Card>

          {/* ── Orchestrator correlation note ─────────────────────── */}
          {stats.orchestrator_runs > 0 && (
            <div className="flex items-start gap-2 rounded-lg border border-violet-100 bg-violet-50 p-4">
              <BarChart3 className="h-5 w-5 text-violet-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-violet-900">Orchestrator Usage</p>
                <p className="text-violet-700 mt-0.5">
                  The orchestrator has been invoked{" "}
                  <strong>{stats.orchestrator_runs.toLocaleString()}</strong> times in
                  the last {period}h — indicating{" "}
                  {stats.orchestrator_runs > 1000
                    ? "high-volume concurrent request handling"
                    : "moderate request routing activity"}
                  .
                </p>
              </div>
            </div>
          )}
        </TabsContent>

        {/* ── Triggers Tab ──────────────────────────────────────────── */}
        <TabsContent value="triggers" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Zap className="h-5 w-5 text-amber-500" />
                Trigger Distribution — Last {period}h
              </CardTitle>
              <CardDescription>
                Which events are most frequently triggering agent runs
              </CardDescription>
            </CardHeader>
            <CardContent>
              <TriggerDistributionChart triggers={stats.trigger_distribution} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Failures Tab ──────────────────────────────────────────── */}
        <TabsContent value="failures" className="space-y-4 mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-red-500" />
                Recent Failures — Last {period}h
              </CardTitle>
              <CardDescription>
                {stats.recent_failures.length > 0
                  ? `${stats.recent_failures.length} failure(s) detected. Click a failure to see full details.`
                  : "No failures detected in this period — all agents healthy."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RecentFailuresList failures={stats.recent_failures} />
            </CardContent>
          </Card>

          {/* ── Failure by agent breakdown ────────────────────────── */}
          {Object.keys(stats.failure_summary.by_agent).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Failures by Agent</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(stats.failure_summary.by_agent).map(
                    ([agentName, count]) => (
                      <div
                        key={agentName}
                        className="flex items-center gap-2 rounded-lg border px-4 py-2"
                      >
                        <AgentBadge name={agentName} />
                        <span className="font-bold text-red-600">{count}</span>
                        <span className="text-xs text-muted-foreground">failures</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
