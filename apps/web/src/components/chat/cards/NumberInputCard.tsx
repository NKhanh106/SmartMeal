"use client";

import { useState, useCallback } from "react";
import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

interface NumberInputCardProps {
  value: number | null;
  onChange: (value: number | null) => void;
  min?: number | null;
  max?: number | null;
  unit?: string | null;
  placeholder?: string | null;
}

export function NumberInputCard({
  value,
  onChange,
  min = 0,
  max = 9999,
  unit,
  placeholder,
}: NumberInputCardProps) {
  const displayValue = value ?? "";

  const [inputStr, setInputStr] = useState(String(value ?? ""));

  const handleInputChange = useCallback(
    (raw: string) => {
      // Allow empty
      if (raw === "") {
        setInputStr("");
        onChange(null);
        return;
      }
      // Only allow digits and decimal point
      const cleaned = raw.replace(/[^0-9.]/g, "");
      // Prevent multiple decimals
      const parts = cleaned.split(".");
      const sanitized = parts.length > 2 ? parts[0] + "." + parts.slice(1).join("") : cleaned;

      setInputStr(sanitized);

      const num = parseFloat(sanitized);
      if (!isNaN(num)) {
        const clamped = Math.min(Math.max(num, min ?? -Infinity), max ?? Infinity);
        onChange(clamped);
      }
    },
    [min, max, onChange]
  );

  const step = 1;
  const effectiveMin = min ?? 0;
  const effectiveMax = max ?? 9999;

  function increment() {
    const current = value ?? (min ?? 0);
    const next = Math.min(current + step, effectiveMax);
    onChange(next);
    setInputStr(String(next));
  }

  function decrement() {
    const current = value ?? (min ?? 0);
    const next = Math.max(current - step, effectiveMin);
    onChange(next);
    setInputStr(String(next));
  }

  const isOutOfRange =
    value !== null && (value < effectiveMin || value > effectiveMax);

  const rangeHint =
    min !== null || max !== null
      ? [
          min !== null ? `Tối thiểu: ${min}` : null,
          max !== null ? `Tối đa: ${max}` : null,
        ]
          .filter(Boolean)
          .join(" · ")
      : null;

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Main input row */}
      <div className="flex items-center gap-3">
        {/* Decrement */}
        <button
          type="button"
          onClick={decrement}
          disabled={value !== null && value <= effectiveMin}
          className={cn(
            "flex-shrink-0 w-12 h-12 rounded-xl border-2 border-slate-200 flex items-center justify-center transition-all",
            "hover:border-emerald-400 hover:bg-emerald-50 active:scale-95",
            "disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:border-slate-200 disabled:hover:bg-white"
          )}
          aria-label="Giảm"
        >
          <Minus className="h-5 w-5 text-slate-600" />
        </button>

        {/* Number field */}
        <div className="relative flex items-baseline">
          <input
            type="text"
            inputMode="decimal"
            className={cn(
              "w-28 h-14 text-center text-2xl font-bold rounded-xl border-2 transition-all",
              "focus:outline-none focus:ring-0",
              isOutOfRange
                ? "border-red-400 bg-red-50 text-red-700"
                : "border-slate-200 bg-white text-slate-900 focus:border-emerald-400 focus:bg-emerald-50"
            )}
            value={displayValue}
            placeholder={placeholder ?? ""}
            onChange={(e) => handleInputChange(e.target.value)}
            onBlur={() => {
              // Snap to valid range on blur
              if (value !== null && isOutOfRange) {
                const clamped = Math.min(Math.max(value, effectiveMin), effectiveMax);
                onChange(clamped);
                setInputStr(String(clamped));
              }
            }}
          />
          {unit && (
            <span className="ml-2 text-base font-medium text-slate-500">{unit}</span>
          )}
        </div>

        {/* Increment */}
        <button
          type="button"
          onClick={increment}
          disabled={value !== null && value >= effectiveMax}
          className={cn(
            "flex-shrink-0 w-12 h-12 rounded-xl border-2 border-slate-200 flex items-center justify-center transition-all",
            "hover:border-emerald-400 hover:bg-emerald-50 active:scale-95",
            "disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:border-slate-200 disabled:hover:bg-white"
          )}
          aria-label="Tăng"
        >
          <Plus className="h-5 w-5 text-slate-600" />
        </button>
      </div>

      {/* Range hint */}
      {rangeHint && (
        <p className="text-xs text-slate-400">{rangeHint}</p>
      )}
    </div>
  );
}
