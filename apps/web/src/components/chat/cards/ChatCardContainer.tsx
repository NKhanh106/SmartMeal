"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { SingleSelectCard } from "./SingleSelectCard";
import { MultiSelectCard } from "./MultiSelectCard";
import { RankCard } from "./RankCard";
import { NumberInputCard } from "./NumberInputCard";
import { ConfirmCard } from "./ConfirmCard";
import type { ChatCard, ChatCardResponse } from "@/components/chatbot/types";

interface ChatCardContainerProps {
  card: ChatCard;
  onSubmit: (response: ChatCardResponse) => void;
  onSkip: () => void;
  isLoading?: boolean;
}

// Local response state per card type
interface LocalState {
  singleSelect: string | null;
  multiSelect: string[];
  rank: string[];
  number: number | null;
  confirm: boolean | null;
}

export function ChatCardContainer({
  card,
  onSubmit,
  onSkip,
  isLoading = false,
}: ChatCardContainerProps) {
  const initial: LocalState = {
    singleSelect: null,
    multiSelect: [],
    rank: card.options?.map((o) => o.id) ?? [],
    number: null,
    confirm: null,
  };

  const [state, setState] = useState<LocalState>(initial);

  function submit() {
    const base = { card_id: card.card_id, card_type: card.card_type };

    switch (card.card_type) {
      case "single_select":
        if (state.singleSelect) {
          onSubmit({ ...base, selected_ids: [state.singleSelect] });
        }
        break;
      case "multi_select":
        onSubmit({ ...base, selected_ids: state.multiSelect });
        break;
      case "rank":
        onSubmit({ ...base, ranked_ids: state.rank });
        break;
      case "number_input":
        onSubmit({ ...base, number_value: state.number });
        break;
      case "confirm":
        if (state.confirm !== null) {
          onSubmit({ ...base, confirmed: state.confirm });
        }
        break;
    }
  }

  const canSubmit = (() => {
    switch (card.card_type) {
      case "single_select":
        return state.singleSelect !== null;
      case "multi_select": {
        const min = card.min_selections ?? 0;
        return state.multiSelect.length >= min;
      }
      case "rank":
        return card.options
          ? state.rank.length === card.options.length
          : false;
      case "number_input": {
        if (state.number === null) return false;
        const min = card.min_value ?? -Infinity;
        const max = card.max_value ?? Infinity;
        return state.number >= min && state.number <= max;
      }
      case "confirm":
        return state.confirm !== null;
      default:
        return false;
    }
  })();

  function handleSingleSelect(id: string) {
    setState((s) => ({ ...s, singleSelect: id }));
    // Auto-submit single select immediately
    onSubmit({
      card_id: card.card_id,
      card_type: card.card_type,
      selected_ids: [id],
    });
  }

  function handleMultiSelect(id: string) {
    setState((s) => {
      const already = s.multiSelect.includes(id);
      const max = card.max_selections ?? card.options?.length ?? s.multiSelect.length + 1;
      if (already) {
        return { ...s, multiSelect: s.multiSelect.filter((x) => x !== id) };
      }
      if (s.multiSelect.length >= max) return s;
      return { ...s, multiSelect: [...s.multiSelect, id] };
    });
  }

  function handleRank(newOrder: string[]) {
    setState((s) => ({ ...s, rank: newOrder }));
  }

  function handleNumberChange(val: number | null) {
    setState((s) => ({ ...s, number: val }));
  }

  function handleConfirm(val: boolean) {
    setState((s) => ({ ...s, confirm: val }));
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.97 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mx-4 mb-2"
    >
      <div
        className="rounded-2xl border-l-4 border-emerald-500 bg-white p-4 shadow-lg shadow-slate-200/60"
        style={{ borderLeftWidth: "3px" }}
      >
        {/* Header */}
        <div className="mb-4">
          <h3 className="font-semibold text-slate-900 leading-tight">{card.title}</h3>
          {card.subtitle && (
            <p className="text-sm text-slate-500 mt-1 leading-relaxed">{card.subtitle}</p>
          )}
        </div>

        {/* Card body */}
        <div>
          {card.card_type === "single_select" && card.options && (
            <SingleSelectCard
              options={card.options}
              selectedId={state.singleSelect}
              onSelect={handleSingleSelect}
            />
          )}

          {card.card_type === "multi_select" && card.options && (
            <MultiSelectCard
              options={card.options}
              selectedIds={state.multiSelect}
              minSelections={card.min_selections}
              maxSelections={card.max_selections}
              onToggle={handleMultiSelect}
            />
          )}

          {card.card_type === "rank" && card.options && (
            <RankCard
              options={card.options}
              orderedIds={state.rank}
              onReorder={handleRank}
            />
          )}

          {card.card_type === "number_input" && (
            <NumberInputCard
              value={state.number}
              onChange={handleNumberChange}
              min={card.min_value}
              max={card.max_value}
              unit={card.unit}
              placeholder={card.placeholder}
            />
          )}

          {card.card_type === "confirm" && (
            <ConfirmCard confirmed={state.confirm} onConfirm={handleConfirm} />
          )}
        </div>

        {/* Footer — only for multi/rank/number/confirm */}
        {card.card_type !== "single_select" && (
          <div className="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-slate-100">
            {card.skippable && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onSkip}
                disabled={isLoading}
                className="text-slate-400 hover:text-slate-600 h-8 px-2 text-xs"
              >
                Bỏ qua
              </Button>
            )}
            <Button
              size="sm"
              onClick={submit}
              disabled={!canSubmit || isLoading}
              className="h-8 px-4 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-medium shadow-sm"
            >
              {isLoading ? "Đang xử lý..." : "Xác nhận"}
            </Button>
          </div>
        )}
      </div>
    </motion.div>
  );
}
