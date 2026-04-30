"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Minus, Bot } from "lucide-react";

interface ChatHeaderProps {
  onMinimize: () => void;
  onClose: () => void;
}

export function ChatHeader({ onMinimize, onClose: _onClose }: ChatHeaderProps) {
  return (
    <div className="flex items-center justify-between px-6 py-4 bg-emerald-500 text-white">
      {/* Left: bot avatar + info */}
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 bg-white/20 rounded-xl flex items-center justify-center">
          <Bot className="h-6 w-6" />
        </div>
        <div>
          <h3 className="font-bold text-sm">SmartMeal Assistant</h3>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 bg-emerald-200 rounded-full animate-pulse" />
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-50">
              Sẵn sàng hỗ trợ
            </span>
          </div>
        </div>
      </div>

      {/* Right: minimize */}
      <button
        onClick={onMinimize}
        className="flex h-8 w-8 items-center justify-center rounded-full text-white hover:bg-white/20 transition-colors"
        aria-label="Thu nhỏ"
      >
        <Minus className="h-5 w-5" />
      </button>
    </div>
  );
}
