"use client";

import { useChatBot } from "@/hooks/use-chatbot";
import { ChatBubble } from "./ChatBubble";
import { ChatPanel } from "./ChatPanel";

export function FloatingChatBot() {
  const { isOpen, messages, inputValue, isTyping, isLoadingHistory, setInputValue, toggleChat, closeChat, sendMessageStream } =
    useChatBot();

  const handleSend = () => {
    if (inputValue.trim()) {
      sendMessageStream(inputValue);
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
