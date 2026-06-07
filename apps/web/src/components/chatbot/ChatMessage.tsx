"use client";

import { Bot, RefreshCw, User } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/components/chatbot/types";

interface ChatMessageProps {
  message: ChatMessageType;
  onRetry?: () => void;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const DEPTH_BADGE_CLASSES: Record<string, string> = {
  quick: "border-amber-200 text-amber-600 bg-amber-50",
  deep: "border-emerald-200 text-emerald-600 bg-emerald-50",
  expert: "border-violet-200 text-violet-600 bg-violet-50",
};

const DEPTH_BADGE_ICONS: Record<string, string> = {
  quick: "⚡",
  deep: "🔍",
  expert: "🧠",
};

export function ChatMessage({ message, onRetry }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isError = message.isError === true;

  return (
    <div
      className={cn(
        "flex gap-3 max-w-[85%]",
        isUser ? "ml-auto flex-row-reverse" : "mr-auto"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm border",
          isUser
            ? "bg-slate-50 border-slate-100 text-slate-600"
            : isError
            ? "bg-red-50 border-red-100 text-red-500"
            : "bg-emerald-50 border-emerald-100 text-emerald-600"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "px-4 py-3 rounded-2xl text-sm leading-relaxed",
          isUser
            ? "bg-emerald-500 text-white rounded-tr-none shadow-md shadow-emerald-500/20"
            : isError
            ? "bg-red-50 text-red-800 rounded-tl-none border border-red-100"
            : "bg-slate-50 text-slate-800 rounded-tl-none border border-slate-100"
        )}
      >
        {!message.content && message.isStreaming && !isUser ? (
          <div className="flex items-center gap-1 h-5 py-1">
            <motion.div
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ repeat: Infinity, duration: 1, delay: 0 }}
              className="h-1.5 w-1.5 bg-slate-400 rounded-full"
            />
            <motion.div
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ repeat: Infinity, duration: 1, delay: 0.2 }}
              className="h-1.5 w-1.5 bg-slate-400 rounded-full"
            />
            <motion.div
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ repeat: Infinity, duration: 1, delay: 0.4 }}
              className="h-1.5 w-1.5 bg-slate-400 rounded-full"
            />
          </div>
        ) : (
          <>
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
            {message.isStreaming && !isUser && (
              <span className="inline-block w-2 h-3.5 bg-slate-400 animate-pulse ml-0.5 mt-0.5 rounded-sm align-middle" />
            )}
          </>
        )}

        {/* Footer: depth badge + timestamp */}
        <div
          className={cn(
            "text-[10px] mt-1.5 opacity-50 font-bold uppercase",
            isUser ? "text-right" : "text-left"
          )}
        >
          <span className="inline-flex items-center gap-1">
            {formatTime(message.timestamp)}
            {!isUser && message.depth && (
              <span
                className={cn(
                  "inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full border ml-2 opacity-60",
                  DEPTH_BADGE_CLASSES[message.depth] ?? ""
                )}
              >
                {DEPTH_BADGE_ICONS[message.depth]}
              </span>
            )}
          </span>
        </div>
        {isError && onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 flex items-center gap-1 text-xs text-red-500 hover:text-red-700 transition-colors"
          >
            <RefreshCw className="h-3 w-3" />
            Thử lại
          </button>
        )}
      </div>
    </div>
  );
}
