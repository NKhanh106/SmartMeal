"use client";

import { motion } from "framer-motion";
import { Bot, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatBubbleProps {
  isOpen: boolean;
  onClick: () => void;
}

export function ChatBubble({ isOpen, onClick }: ChatBubbleProps) {
  return (
    <motion.button
      id="chat-bubble"
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      onClick={onClick}
      className={cn(
        "fixed bottom-6 right-6 z-[100] flex h-16 w-16 items-center justify-center rounded-full shadow-2xl transition-all duration-300",
        isOpen
          ? "bg-slate-200 text-slate-600 rotate-90"
          : "bg-gradient-to-br from-emerald-400 to-emerald-600 text-white"
      )}
    >
      {isOpen ? (
        <span className="text-2xl font-bold leading-none">×</span>
      ) : (
        <div className="relative">
          <Bot className="h-8 w-8" />
          <motion.div
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.5, 1, 0.5],
            }}
            transition={{
              repeat: Infinity,
              duration: 2,
            }}
            className="absolute -top-1 -right-1"
          >
            <Sparkles className="h-4 w-4 text-emerald-200 fill-emerald-200" />
          </motion.div>
        </div>
      )}
    </motion.button>
  );
}
