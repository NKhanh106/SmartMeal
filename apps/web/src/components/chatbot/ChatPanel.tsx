"use client";

import { motion, AnimatePresence } from "framer-motion";
import { ChatHeader } from "./ChatHeader";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";
import type { ChatMessage } from "./types";

interface ChatPanelProps {
  isOpen: boolean;
  messages: ChatMessage[];
  inputValue: string;
  isTyping: boolean;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onMinimize: () => void;
  onClose: () => void;
}

export function ChatPanel({
  isOpen,
  messages,
  inputValue,
  isTyping,
  onInputChange,
  onSend,
  onMinimize,
}: ChatPanelProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20, transformOrigin: "bottom right" }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="fixed bottom-24 right-6 z-[100] flex flex-col w-[90vw] sm:w-[400px] h-[70vh] max-h-[650px] bg-white rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.2)] border border-slate-100 overflow-hidden"
        >
          <ChatHeader onMinimize={onMinimize} onClose={onMinimize} />
          <ChatMessageList messages={messages} isTyping={isTyping} />
          <ChatInput
            value={inputValue}
            onChange={onInputChange}
            onSend={onSend}
            disabled={isTyping}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
