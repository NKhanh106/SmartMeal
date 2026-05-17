"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CardOption } from "@/components/chatbot/types";

interface SingleSelectCardProps {
  options: CardOption[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function SingleSelectCard({ options, selectedId, onSelect }: SingleSelectCardProps) {
  const cols = options.length > 4 ? 3 : 2;

  return (
    <div
      className={cn(
        "grid gap-3",
        cols === 2 ? "grid-cols-2" : "grid-cols-2 md:grid-cols-3"
      )}
    >
      {options.map((opt) => {
        const isSelected = selectedId === opt.id;
        return (
          <button
            key={opt.id}
            onClick={() => onSelect(opt.id)}
            className={cn(
              "relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all text-center",
              "hover:shadow-md active:scale-[0.98]",
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
  );
}
