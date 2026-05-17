"use client";

import { AlertTriangle, Info } from "lucide-react";
import type { ChatCard, ChatCardResponse } from "../types";

interface ConfirmCardProps {
  card: ChatCard;
  onSubmit: (response: ChatCardResponse) => void;
  isLoading: boolean;
}

export function ConfirmCard({ card, onSubmit, isLoading }: ConfirmCardProps) {
  const isMedical = card.trigger_reason === "missing_health_conditions";

  return (
    <div className="space-y-4">
      {/* Icon */}
      <div className="flex justify-center">
        {isMedical ? (
          <div className="h-12 w-12 rounded-full bg-amber-50 border border-amber-100 flex items-center justify-center">
            <AlertTriangle className="h-6 w-6 text-amber-500" />
          </div>
        ) : (
          <div className="h-12 w-12 rounded-full bg-blue-50 border border-blue-100 flex items-center justify-center">
            <Info className="h-6 w-6 text-blue-500" />
          </div>
        )}
      </div>

      {/* Two buttons */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() =>
            onSubmit({
              card_id: card.card_id,
              card_type: card.card_type,
              confirmed: true,
            })
          }
          disabled={isLoading}
          className="py-3 rounded-xl bg-emerald-500 text-white text-sm font-semibold
                     hover:bg-emerald-600 active:bg-emerald-700
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Có
        </button>
        <button
          onClick={() =>
            onSubmit({
              card_id: card.card_id,
              card_type: card.card_type,
              confirmed: false,
            })
          }
          disabled={isLoading}
          className="py-3 rounded-xl border-2 border-slate-200 text-slate-600 text-sm font-semibold
                     hover:bg-slate-50 hover:border-slate-300 active:bg-slate-100
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Không
        </button>
      </div>
    </div>
  );
}
