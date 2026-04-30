"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence } from "framer-motion";
import { motion } from "framer-motion";
import { ChatMessage } from "./ChatMessage";
import type { ChatMessage as ChatMessageType } from "./types";

interface ChatMessageListProps {
  messages: ChatMessageType[];
  isTyping: boolean;
}

export function ChatMessageList({ messages, isTyping }: ChatMessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = scrollRef.current?.querySelector("[data-radix-scroll-area-viewport]");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages, isTyping]);

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
      <div className="space-y-6 pb-4">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        <AnimatePresence>
          {isTyping && (
            <div className="flex gap-3 max-w-[85%] mr-auto">
              {/* Bot avatar */}
              <div className="h-8 w-8 rounded-full bg-emerald-50 border border-emerald-100 text-emerald-600 flex items-center justify-center flex-shrink-0">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v.704c0 .597.237 1.17.659 1.591l6.341 5.735a2.25 2.25 0 001.659.591M18 14.25v4.5m0 0h4.5m-4.5 0v-4.5M5.25 14.25h13.5c.624 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H5.25a1.125 1.125 0 00-1.125 1.125v1.5c0 .621.501 1.125 1.125 1.125z" />
                </svg>
              </div>
              {/* Typing bubble */}
              <div className="bg-slate-50 px-4 py-3 rounded-2xl rounded-tl-none border border-slate-100 flex items-center gap-1">
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
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
