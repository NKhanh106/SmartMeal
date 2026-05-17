"use client";

import { useState } from "react";
import { useChatBot } from "@/hooks/use-chatbot";
import { ChatBubble } from "./ChatBubble";
import { ChatPanel } from "./ChatPanel";

export function FloatingChatBot() {
  const {
    isOpen,
    messages,
    mealLogs,
    inputValue,
    isTyping,
    isLoadingHistory,
    currentSession,
    sessions,
    staleWarning,
    pendingCard,
    isCardLoading,
    setInputValue,
    openChat,
    closeChat,
    toggleChat,
    sendMessageStream,
    startNewSession,
    switchSession,
    removeSession,
    updateSessionTitle,
    dismissStaleWarning,
    editMealLog,
    removeMealLog,
    retryLastMessage,
    submitCardResponse,
    skipCard,
  } = useChatBot();

  const [showSidebar, setShowSidebar] = useState(false);

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
        mealLogs={mealLogs}
        inputValue={inputValue}
        isTyping={isTyping}
        isLoading={isLoadingHistory}
        currentSession={currentSession}
        sessions={sessions}
        staleWarning={staleWarning}
        showSidebar={showSidebar}
        pendingCard={pendingCard}
        isCardLoading={isCardLoading}
        onInputChange={setInputValue}
        onSend={handleSend}
        onMinimize={closeChat}
        onToggleSidebar={() => setShowSidebar((prev) => !prev)}
        onSelectSession={(session) => {
          switchSession(session);
          setShowSidebar(false);
        }}
        onNewChat={startNewSession}
        onDeleteSession={removeSession}
        onRenameSession={updateSessionTitle}
        onDismissStale={dismissStaleWarning}
        onStartNewChat={startNewSession}
        onEditMealLog={editMealLog}
        onRemoveMealLog={removeMealLog}
        onRetry={retryLastMessage}
        onSubmitCard={submitCardResponse}
        onSkipCard={skipCard}
      />
    </>
  );
}
