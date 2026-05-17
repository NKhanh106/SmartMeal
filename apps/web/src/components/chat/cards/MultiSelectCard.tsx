"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CardOption } from "@/components/chatbot/types";

interface MultiSelectCardProps {
  options: CardOption[];
  selectedIds: string[];
  minSelections?: number | null;
  maxSelections?: number | null;
  onToggle: (id: string) => void;
}

export function MultiSelectCard({
  options,
  selectedIds,
  minSelections,
  maxSelections,
  onToggle,
}: MultiSelectCardProps) {
  const count = selectedIds.length;
  const min = minSelections ?? 0;
  const max = maxSelections ?? options.length;
  const disabled = count >= max;

  const hint =
    min > 0 && count < min
      ? `Cần chọn ít nhất ${min} tùy chọn`
      : max > 0 && count >= max
      ? `Đã chọn đủ ${max} tùy chọn`
      : count > 0
      ? `Đã chọn ${count}/${max}`
      : null;

  return (
    <div className="space-y-3">
      {hint && (
        <p className={cn(
          "text-xs font-medium",
          count >= min ? "text-emerald-600" : "text-slate-500"
        )}>
          {hint}
        </p>
      )}
      <div className="grid grid-cols-2 gap-3">
        {options.map((opt) => {
          const isSelected = selectedIds.includes(opt.id);
          return (
            <button
              key={opt.id}
              onClick={() => {
                if (isSelected) {
                  onToggle(opt.id);
                } else if (!disabled) {
                  onToggle(opt.id);
                }
              }}
              disabled={!isSelected && disabled}
              className={cn(
                "relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all text-center",
                !isSelected && disabled && "opacity-40 cursor-not-allowed",
                !isSelected && !disabled && "hover:shadow-sm active:scale-[0.98]",
                isSelected
                  ? "border-emerald-500 bg-emerald-50 text-emerald-900 shadow-sm"
                  : "border-slate-200 bg-white text-slate-700 hover:border-emerald-200 hover:bg-emerald-50/50"
              )}
            >
              {isSelected && (
                <span className="absolute top-2 right-2 rounded-full bg-emerald-500 p-0.5">
                  <Check className="h-3 w-3 text-white" strokeWidth={3} />
                </span>
              )}
              {opt.icon && (
                <span className="text-3xl leading-none" role="img" aria-hidden="true">
                  {opt.icon}
                </span>
              )}
              <span className="text-sm font-medium leading-tight">{opt.label}</span>
              {opt.description && (
                <span className="text-xs text-slate-400 leading-tight">{opt.description}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
