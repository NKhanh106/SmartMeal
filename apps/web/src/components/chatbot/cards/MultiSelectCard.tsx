"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import type { ChatCard, ChatCardResponse } from "../types";

interface MultiSelectCardProps {
  card: ChatCard;
  onSubmit: (response: ChatCardResponse) => void;
  isLoading: boolean;
}

export function MultiSelectCard({ card, onSubmit, isLoading }: MultiSelectCardProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const options = card.options || [];
  const minSelections = card.min_selections || 0;
  const maxSelections = card.max_selections || options.length;

  const toggleOption = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < maxSelections) {
        next.add(id);
      }
      return next;
    });
  };

  const handleSubmit = () => {
    if (selectedIds.size < minSelections) return;
    onSubmit({
      card_id: card.card_id,
      card_type: card.card_type,
      selected_ids: Array.from(selectedIds),
    });
  };

  const canSubmit = selectedIds.size >= minSelections && selectedIds.size <= maxSelections;

  return (
    <div className="space-y-3">
      {minSelections > 0 && (
        <p className="text-xs text-slate-400">
          {selectedIds.size < minSelections
            ? `Chọn ít nhất ${minSelections} mục (${selectedIds.size}/${minSelections})`
            : `${selectedIds.size} đã chọn${maxSelections ? ` / tối đa ${maxSelections}` : ""}`}
        </p>
      )}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-2">
        {options.map((opt) => {
          const isSelected = selectedIds.has(opt.id);
          return (
            <button
              key={opt.id}
              onClick={() => toggleOption(opt.id)}
              disabled={isLoading || (!isSelected && selectedIds.size >= maxSelections)}
              className={`
                relative flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 text-left
                transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed
                ${isSelected
                  ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                }
              `}
            >
              {isSelected && (
                <span className="absolute top-1.5 left-1.5">
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                </span>
              )}
              {opt.icon && <span className="text-lg leading-none">{opt.icon}</span>}
              <span className="text-sm font-medium flex-1 leading-tight pl-5">{opt.label}</span>
            </button>
          );
        })}
      </div>
      <button
        onClick={handleSubmit}
        disabled={!canSubmit || isLoading}
        className="w-full py-2.5 rounded-xl bg-emerald-500 text-white text-sm font-semibold
                   hover:bg-emerald-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? "Đang xử lý..." : `Xác nhận${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
      </button>
    </div>
  );
}
