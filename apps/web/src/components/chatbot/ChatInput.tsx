"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ value, onChange, onSend, disabled, placeholder = "Nhập yêu cầu của bạn..." }: ChatInputProps) {
  const [localValue, setLocalValue] = useState(value);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
    }
  }, [localValue]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const canSend = localValue.trim().length > 0 && !disabled;

  return (
    <div className="p-4 bg-white border-t border-slate-50">
      {/* Input wrapper — matches Google AI Studio original */}
      <div className="flex gap-2 p-1.5 bg-slate-50 rounded-2xl border border-slate-100 focus-within:ring-2 focus-within:ring-emerald-500/20 focus-within:bg-white transition-all">
        <textarea
          ref={textareaRef}
          rows={1}
          className="flex-1 border-none bg-transparent focus-visible:ring-0 focus-visible:outline-none shadow-none h-10 px-3 text-sm resize-none placeholder:text-slate-400"
          placeholder={placeholder}
          value={localValue}
          onChange={(e) => {
            setLocalValue(e.target.value);
            onChange(e.target.value);
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <Button
          size="icon"
          onClick={onSend}
          disabled={!canSend}
          className="h-10 w-10 rounded-xl bg-emerald-500 hover:bg-emerald-600 shadow-lg shadow-emerald-500/20 shrink-0"
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
