"use client";

import { useRef, useEffect, KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DepthSelector, type DepthMode } from "./DepthSelector";

interface ChatInputProps {
  value: string;
  depth: DepthMode;
  onChange: (value: string) => void;
  onDepthChange: (depth: DepthMode) => void;
  onSend: () => void;
  disabled?: boolean;
  placeholder?: string;
}

const DEPTH_HINTS: Record<DepthMode, string> = {
  quick: "⚡ Trả lời nhanh, không phân tích sâu",
  deep: "🔍 Tư vấn có phân tích sức khỏe",
  expert: "🧠 Tư vấn toàn diện từ nhiều chuyên gia",
};

const PLACEHOLDERS: Record<DepthMode, string> = {
  quick: "Hỏi nhanh...",
  deep: "Nhắn tin...",
  expert: "Hỏi bất kỳ điều gì — tư vấn toàn diện...",
};

const BUTTON_COLORS: Record<DepthMode, string> = {
  quick: "bg-amber-500 hover:bg-amber-600 shadow-amber-500/20",
  deep: "bg-emerald-500 hover:bg-emerald-600 shadow-emerald-500/20",
  expert: "bg-violet-500 hover:bg-violet-600 shadow-violet-500/20",
};

export function ChatInput({
  value,
  depth,
  onChange,
  onDepthChange,
  onSend,
  disabled,
  placeholder,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
    }
  }, [value]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim().length > 0 && !disabled) {
        onSend();
      }
    }
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="p-4 bg-white border-t border-slate-50">
      {/* Depth Selector Bar */}
      <div className="flex items-center justify-between mb-2">
        <DepthSelector
          value={depth}
          onChange={onDepthChange}
          disabled={disabled}
        />
        <span className="text-[11px] text-slate-400 hidden sm:block">
          {DEPTH_HINTS[depth]}
        </span>
      </div>

      {/* Input wrapper */}
      <div className="flex gap-2 p-1.5 bg-slate-50 rounded-2xl border border-slate-100 focus-within:ring-2 focus-within:ring-emerald-500/20 focus-within:bg-white transition-all">
        <textarea
          ref={textareaRef}
          rows={1}
          className="flex-1 border-none bg-transparent focus-visible:ring-0 focus-visible:outline-none shadow-none h-10 px-3 text-sm resize-none placeholder:text-slate-400"
          placeholder={placeholder ?? PLACEHOLDERS[depth]}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <Button
          size="icon"
          onClick={onSend}
          disabled={!canSend}
          className={`h-10 w-10 rounded-xl shadow-lg ${BUTTON_COLORS[depth]} shrink-0`}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>

      {/* Disclaimer */}
      <p className="text-[10px] text-center text-slate-400 mt-3 flex items-center justify-center gap-1">
        <svg
          className="h-3 w-3 shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
          />
        </svg>
        AI có thể trả lời sai, vui lòng kiểm tra lại thông tin.
      </p>
    </div>
  );
}
