"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import type { ChatCard, ChatCardResponse } from "../types";
import { SingleSelectCard } from "./SingleSelectCard";
import { MultiSelectCard } from "./MultiSelectCard";
import { RankCard } from "./RankCard";
import { NumberInputCard } from "./NumberInputCard";
import { ConfirmCard } from "./ConfirmCard";

interface ChatCardContainerProps {
  card: ChatCard;
  onSubmit: (response: ChatCardResponse) => void;
  onSkip: () => void;
  isLoading?: boolean;
}

export function ChatCardContainer({
  card,
  onSubmit,
  onSkip,
  isLoading = false,
}: ChatCardContainerProps) {
  const innerCard = () => {
    switch (card.card_type) {
      case "single_select":
        return <SingleSelectCard card={card} onSubmit={onSubmit} isLoading={isLoading} />;
      case "multi_select":
        return <MultiSelectCard card={card} onSubmit={onSubmit} isLoading={isLoading} />;
      case "rank":
        return <RankCard card={card} onSubmit={onSubmit} isLoading={isLoading} />;
      case "number_input":
        return <NumberInputCard card={card} onSubmit={onSubmit} isLoading={isLoading} />;
      case "confirm":
        return <ConfirmCard card={card} onSubmit={onSubmit} isLoading={isLoading} />;
      default:
        return null;
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.98 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="bg-white rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.08)] border-l-[3px] border-l-emerald-500 overflow-hidden"
    >
      <div className="px-4 pt-4 pb-0">
        <h3 className="font-semibold text-gray-900 text-base leading-snug">{card.title}</h3>
        {card.subtitle && (
          <p className="text-sm text-slate-500 mt-1 leading-relaxed">{card.subtitle}</p>
        )}
      </div>
      <div className="px-4 py-4">{innerCard()}</div>
      {(card.skippable || isLoading) && (
        <div className="px-4 pb-4 flex items-center justify-end gap-3">
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Đang xử lý...</span>
            </div>
          )}
          {card.skippable && !isLoading && (
            <button
              onClick={onSkip}
              className="text-sm text-slate-400 hover:text-slate-600 transition-colors px-2 py-1 rounded-lg hover:bg-slate-50"
            >
              Bỏ qua
            </button>
          )}
        </div>
      )}
    </motion.div>
  );
}
