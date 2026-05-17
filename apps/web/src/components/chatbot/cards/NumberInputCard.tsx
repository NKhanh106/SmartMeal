"use client";

import { useState } from "react";
import { Minus, Plus } from "lucide-react";
import type { ChatCard, ChatCardResponse } from "../types";

interface NumberInputCardProps {
  card: ChatCard;
  onSubmit: (response: ChatCardResponse) => void;
  isLoading: boolean;
}

export function NumberInputCard({ card, onSubmit, isLoading }: NumberInputCardProps) {
  const min = card.min_value ?? 0;
  const max = card.max_value ?? 999;
  const [inputValue, setInputValue] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const numValue = parseFloat(inputValue);
  const isValid =
    inputValue.trim() !== "" &&
    !isNaN(numValue) &&
    numValue >= min &&
    numValue <= max;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    // Allow only numbers and decimal point
    if (!/^\d*\.?\d*$/.test(val)) return;
    setInputValue(val);
    setError(null);
  };

  const step = (delta: number) => {
    const current = isNaN(numValue) ? min : numValue;
    const next = Math.min(max, Math.max(min, current + delta));
    setInputValue(String(next));
    setError(null);
  };

  const handleSubmit = () => {
    if (!isValid) {
      if (inputValue.trim() === "") {
        setError("Vui lòng nhập giá trị");
      } else if (isNaN(numValue)) {
        setError("Giá trị không hợp lệ");
      } else if (numValue < min) {
        setError(`Giá trị tối thiểu là ${min}`);
      } else if (numValue > max) {
        setError(`Giá trị tối đa là ${max}`);
      }
      return;
    }
    onSubmit({
      card_id: card.card_id,
      card_type: card.card_type,
      number_value: numValue,
    });
  };

  return (
    <div className="space-y-4">
      {/* Input row: [ - ] [ input unit ] [ + ] */}
      <div className="flex items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => step(-1)}
          disabled={isLoading}
          className="h-12 w-12 rounded-xl border-2 border-slate-200 bg-white text-slate-600
                     hover:bg-slate-50 hover:border-slate-300 active:bg-slate-100
                     disabled:opacity-50 flex items-center justify-center transition-colors"
        >
          <Minus className="h-5 w-5" />
        </button>

        <div className="flex items-center gap-1.5">
          <input
            type="text"
            inputMode="decimal"
            value={inputValue}
            onChange={handleChange}
            placeholder={card.placeholder || "0"}
            disabled={isLoading}
            className={`
              w-24 h-12 px-3 text-center text-xl font-semibold rounded-xl border-2
              focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400
              disabled:opacity-50 transition-colors bg-white
              ${error ? "border-red-300 text-red-600" : "border-slate-200 text-slate-900"}
            `}
          />
          {card.unit && (
            <span className="text-base font-medium text-slate-500 w-8">{card.unit}</span>
          )}
        </div>

        <button
          type="button"
          onClick={() => step(1)}
          disabled={isLoading}
          className="h-12 w-12 rounded-xl border-2 border-slate-200 bg-white text-slate-600
                     hover:bg-slate-50 hover:border-slate-300 active:bg-slate-100
                     disabled:opacity-50 flex items-center justify-center transition-colors"
        >
          <Plus className="h-5 w-5" />
        </button>
      </div>

      {/* Min/max hint */}
      <p className="text-center text-xs text-slate-400">
        {min !== 0 || max !== 999
          ? `Tối thiểu ${min}${card.unit ? ` ${card.unit}` : ""} · Tối đa ${max}${card.unit ? ` ${card.unit}` : ""}`
          : "Nhập số vào ô trên"}
      </p>

      {/* Error message */}
      {error && (
        <p className="text-center text-sm text-red-500">{error}</p>
      )}

      <button
        onClick={handleSubmit}
        disabled={!isValid || isLoading}
        className="w-full py-2.5 rounded-xl bg-emerald-500 text-white text-sm font-semibold
                   hover:bg-emerald-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? "Đang xử lý..." : "Xác nhận"}
      </button>
    </div>
  );
}
