"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import type { ChatCard, ChatCardResponse } from "../types";

interface SingleSelectCardProps {
  card: ChatCard;
  onSubmit: (response: ChatCardResponse) => void;
  isLoading: boolean;
}

export function SingleSelectCard({ card, onSubmit, isLoading }: SingleSelectCardProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const options = card.options || [];
  const cols = options.length > 4 ? 3 : 2;

  const handleSubmit = () => {
    if (!selectedId) return;
    onSubmit({
      card_id: card.card_id,
      card_type: card.card_type,
      selected_ids: [selectedId],
    });
  };

  return (
    <div className="space-y-3">
      <div className={`grid grid-cols-2 gap-2 ${cols === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
        {options.map((opt) => {
          const isSelected = selectedId === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => setSelectedId(opt.id)}
              disabled={isLoading}
              className={`
                relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl border-2 text-left
                transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed
                ${isSelected
                  ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                }
              `}
            >
              {opt.icon && <span className="text-lg leading-none">{opt.icon}</span>}
              <span className="text-sm font-medium flex-1 leading-tight">{opt.label}</span>
              {isSelected && (
                <span className="absolute top-1.5 right-1.5">
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                </span>
              )}
            </button>
          );
        })}
      </div>
      <button
        onClick={handleSubmit}
        disabled={!selectedId || isLoading}
        className="w-full py-2.5 rounded-xl bg-emerald-500 text-white text-sm font-semibold
                   hover:bg-emerald-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? "Đang xử lý..." : "Xác nhận"}
      </button>
    </div>
  );
}
