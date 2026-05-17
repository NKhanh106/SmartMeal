"use client";

import { cn } from "@/lib/utils";

interface ConfirmCardProps {
  confirmed: boolean | null;
  onConfirm: (value: boolean) => void;
  showWarning?: boolean;
}

export function ConfirmCard({ confirmed, onConfirm, showWarning = false }: ConfirmCardProps) {
  return (
    <div className="flex flex-col gap-3">
      {showWarning && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-amber-50 border border-amber-200">
          <span className="text-amber-500 text-sm">⚠️</span>
          <span className="text-xs text-amber-700">
            Thao tác này ảnh hưởng đến dữ liệu sức khỏe của bạn.
          </span>
        </div>
      )}
      <div className="flex gap-3">
        <button
        type="button"
        onClick={() => onConfirm(true)}
        className={cn(
          "flex-1 flex flex-col items-center gap-2 py-5 rounded-xl border-2 font-semibold text-base transition-all active:scale-[0.98]",
          confirmed === true
            ? "border-emerald-500 bg-emerald-500 text-white shadow-md"
            : "border-slate-200 bg-white text-slate-700 hover:border-emerald-400 hover:bg-emerald-50 hover:text-emerald-700"
        )}
      >
        <span className="text-2xl">✓</span>
        Có
      </button>

      <button
        type="button"
        onClick={() => onConfirm(false)}
        className={cn(
          "flex-1 flex flex-col items-center gap-2 py-5 rounded-xl border-2 font-semibold text-base transition-all active:scale-[0.98]",
          confirmed === false
            ? "border-slate-400 bg-slate-100 text-slate-700"
            : "border-slate-200 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50"
        )}
      >
        <span className="text-2xl">✗</span>
        Không
      </button>
    </div>
  );
}
