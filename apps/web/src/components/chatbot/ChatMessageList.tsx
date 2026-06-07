"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence } from "framer-motion";
import { motion } from "framer-motion";
import { ChatMessage } from "./ChatMessage";
import { MealLogCard } from "./MealLogCard";
import { DepthLoadingIndicator } from "./DepthLoadingIndicator";
import type { ChatMessage as ChatMessageType, MealLogCardData } from "./types";
import type { DepthMode } from "./DepthSelector";

interface ChatMessageListProps {
  messages: ChatMessageType[];
  mealLogs?: MealLogCardData[];
  isTyping: boolean;
  depth: DepthMode;
  onEditMealLog?: (id: string, updates: Partial<MealLogCardData>) => void;
  onRemoveMealLog?: (id: string) => void;
  onRetry?: () => void;
}

export function ChatMessageList({
  messages,
  mealLogs = [],
  isTyping,
  depth,
  onEditMealLog,
  onRemoveMealLog,
  onRetry,
}: ChatMessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = scrollRef.current?.querySelector("[data-radix-scroll-area-viewport]");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages, mealLogs, isTyping]);

  const showTypingIndicator = isTyping && !messages.some((m) => m.isStreaming);

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
      <div className="space-y-6 pb-4">
        {messages.length === 0 && mealLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="h-16 w-16 rounded-full bg-emerald-50 flex items-center justify-center mb-4">
              <svg className="h-8 w-8 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-slate-700 mb-2">
              Bạn muốn theo dõi gì hôm nay?
            </h3>
            <p className="text-sm text-slate-500 max-w-xs">
              Tôi có thể hỗ trợ bạn về dinh dưỡng, bữa ăn, luyện tập và mục tiêu sức khỏe.
            </p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} onRetry={msg.isError ? onRetry : undefined} />
            ))}

            {/* Render meal logs that came after the last assistant message */}
            {mealLogs.map((meal, idx) => (
              <motion.div
                key={`meal-${meal.id}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
              >
                <MealLogCard
                  meal={meal}
                  onEdit={onEditMealLog}
                  onRemove={onRemoveMealLog}
                />
              </motion.div>
            ))}
          </>
        )}

        {/* Mode-aware loading indicator */}
        <AnimatePresence>
          {showTypingIndicator && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="flex items-start gap-3 max-w-[85%] mr-auto"
            >
              {/* Bot avatar */}
              <div className="h-8 w-8 rounded-full bg-emerald-50 border border-emerald-100 text-emerald-600 flex items-center justify-center flex-shrink-0">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v.704c0 .597.237 1.17.659 1.591l6.341 5.735a2.25 2.25 0 001.659.591M18 14.25v4.5m0 0h4.5m-4.5 0v-4.5M5.25 14.25h13.5c.624 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H5.25a1.125 1.125 0 00-1.125 1.125v1.5c0 .621.501 1.125 1.125 1.125z" />
                </svg>
              </div>

              {/* Loading indicator */}
              <div className="bg-slate-50 px-4 py-3 rounded-2xl rounded-tl-none border border-slate-100">
                <DepthLoadingIndicator mode={depth} isVisible={true} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
