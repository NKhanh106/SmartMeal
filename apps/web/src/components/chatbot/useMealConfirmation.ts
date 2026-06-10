"use client";

import { useState, useCallback, useEffect } from "react";
import {
  MealConfirmationCard,
  MealConfirmationCardData,
  ExtractedData,
} from "./cards/MealConfirmationCard";

// ─── API Layer ─────────────────────────────────────────────────────────────────

const API_BASE =
  (typeof window !== "undefined"
    ? (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1")
    : "http://localhost:8000/api/v1");

function getToken(): string {
  return localStorage.getItem("access_token") ?? "";
}

async function fetchPendingMealLogs(): Promise<MealConfirmationCardData[]> {
  const res = await fetch(`${API_BASE}/nutrition/pending`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error(`Lỗi khi lấy dữ liệu: ${res.status}`);
  return res.json();
}

async function submitConfirmation(
  logId: string,
  finalData: ExtractedData
): Promise<MealConfirmationCardData> {
  const res = await fetch(`${API_BASE}/nutrition/pending/${logId}/confirm`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${getToken()}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ updated_data: finalData }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Xác nhận thất bại (HTTP ${res.status})`
    );
  }
  return res.json();
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollForPendingMeal(
  intervalMs: number,
  maxAttempts: number,
  onAttempt?: (attempt: number) => void
): Promise<MealConfirmationCardData | null> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    onAttempt?.(attempt);
    const logs = await fetchPendingMealLogs();
    if (logs.length > 0) return logs[0];
    if (attempt < maxAttempts) await sleep(intervalMs);
  }
  return null;
}

// ─── State machine phases ────────────────────────────────────────────────────────

export type PendingMealPhase =
  | "idle"       // chưa bắt đầu
  | "loading"    // đang polling → hiển thị Skeleton
  | "has_data"   // có dữ liệu → hiển thị card
  | "confirming" // đang gọi PATCH
  | "confirmed"  // tích xanh
  | "error";     // có lỗi

// ─── Hook ───────────────────────────────────────────────────────────────────────

interface UseMealConfirmationOptions {
  /** Khoảng thời gian giữa 2 lần poll (ms). Mặc định: 2000 */
  pollIntervalMs?: number;
  /** Số lần poll tối đa. Mặc định: 5 (= 10 giây) */
  maxPollAttempts?: number;
  /** Gọi sau khi xác nhận thành công */
  onConfirmed?: (data: MealConfirmationCardData) => void;
  /** Gọi sau khi hủy */
  onCancelled?: (logId: string) => void;
}

export function useMealConfirmation(options: UseMealConfirmationOptions = {}) {
  const {
    pollIntervalMs = 2000,
    maxPollAttempts = 5,
    onConfirmed,
    onCancelled,
  } = options;

  const [phase, setPhase]     = useState<PendingMealPhase>("idle");
  const [meal, setMeal]       = useState<MealConfirmationCardData | null>(null);
  const [errorMsg, setError]  = useState<string | null>(null);
  const [pollCount, setPollCount] = useState(0);

  // ── Bước 1: Bắt đầu polling sau SSE ──────────────────────────────────────
  const startPolling = useCallback(async () => {
    setPhase("loading");
    setError(null);
    setPollCount(0);

    try {
      const found = await pollForPendingMeal(
        pollIntervalMs,
        maxPollAttempts,
        (attempt) => setPollCount(attempt)
      );
      if (!found) {
        setPhase("idle"); // timeout
        return;
      }
      setMeal(found);
      setPhase("has_data");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Không thể kết nối máy chủ."
      );
      setPhase("error");
    }
  }, [pollIntervalMs, maxPollAttempts]);

  // ── Bước 2: Xác nhận ────────────────────────────────────────────────────────
  const handleConfirm = useCallback(
    async (logId: string, finalData: ExtractedData) => {
      setPhase("confirming");
      try {
        const confirmed = await submitConfirmation(logId, finalData);
        setMeal(confirmed);
        setPhase("confirmed");
        onConfirmed?.(confirmed);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Xác nhận thất bại."
        );
        setPhase("error");
        throw err; // re-throw để card hiển thị lỗi
      }
    },
    [onConfirmed]
  );

  // ── Bước 3: Hủy ────────────────────────────────────────────────────────────
  const handleCancel = useCallback(
    (logId: string) => {
      setPhase("idle");
      setMeal(null);
      setError(null);
      onCancelled?.(logId);
    },
    [onCancelled]
  );

  // ── Auto-reset về idle sau confirmed ──────────────────────────────────────
  useEffect(() => {
    if (phase === "confirmed") {
      const t = setTimeout(() => {
        setPhase("idle");
        setMeal(null);
        setError(null);
      }, 4000);
      return () => clearTimeout(t);
    }
  }, [phase]);

  return {
    phase,
    meal,
    errorMsg,
    pollCount,
    startPolling,
    handleConfirm,
    handleCancel,
  };
}

// ─── Pre-built integration: Card + Polling hook combined ───────────────────────

interface PendingMealCardIntegrationProps extends UseMealConfirmationOptions {}

export function PendingMealCardIntegration(
  props: PendingMealCardIntegrationProps
) {
  const { phase, meal, errorMsg, startPolling, handleConfirm, handleCancel } =
    useMealConfirmation(props);

  // Auto-start polling on mount
  useEffect(() => {
    startPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (phase === "idle") return null;

  if (phase === "loading") {
    return <MealConfirmationCardSkeleton />;
  }

  if (meal) {
    return (
      <MealConfirmationCard
        data={meal}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );
  }

  return null;
}

// ─── Standalone Skeleton (exported for external use) ───────────────────────────

import { Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

function MealConfirmationCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.08)] border border-slate-100 overflow-hidden w-full max-w-md">
      <div className="px-5 pt-5 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-3 mb-3">
          <Skeleton className="h-11 w-11 rounded-xl" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-52" />
            <Skeleton className="h-3 w-32" />
          </div>
        </div>
      </div>
      <div className="px-5 py-4 space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-3 w-24" />
            </div>
            <div className="flex items-center gap-3">
              <Skeleton className="h-8 w-8 rounded-full" />
              <Skeleton className="h-5 w-6" />
              <Skeleton className="h-8 w-8 rounded-full" />
            </div>
          </div>
        ))}
      </div>
      <div className="px-5 pb-5">
        <div className="grid grid-cols-4 gap-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      </div>
      <div className="px-5 pb-5 flex items-center gap-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
        <Skeleton className="h-3 w-64" />
      </div>
    </div>
  );
}
