"use client";

import { useChatBot } from "@/hooks/use-chatbot";
import { ChatBubble } from "./ChatBubble";
import { ChatPanel } from "./ChatPanel";

export function FloatingChatBot() {
  const { isOpen, messages, inputValue, isTyping, setInputValue, toggleChat, closeChat, sendMessage } =
    useChatBot();

  const handleSend = () => {
    if (inputValue.trim()) {
      sendMessage(inputValue);
    }
  };

  return (
    <>
      <ChatBubble onClick={toggleChat} isOpen={isOpen} />
      <ChatPanel
        isOpen={isOpen}
        messages={messages}
        inputValue={inputValue}
        isTyping={isTyping}
        onInputChange={setInputValue}
        onSend={handleSend}
        onMinimize={closeChat}
        onClose={closeChat}
      />
    </>
  );
}
