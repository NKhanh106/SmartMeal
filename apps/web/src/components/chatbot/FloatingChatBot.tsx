"use client";

import { useState, useEffect, useRef } from "react";
import { useChatBot, type DepthMode } from "@/hooks/use-chatbot";
import { ChatBubble } from "./ChatBubble";
import { ChatPanel } from "./ChatPanel";
import { useMealConfirmation } from "./useMealConfirmation";

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
    depth,
    setDepth,
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
    pendingProposals,
    proposalLoading,
    confirmProposal,
    rejectProposal,
  } = useChatBot();

  const [showSidebar, setShowSidebar] = useState(false);

  // Meal confirmation hook
  const {
    phase: mealPhase,
    meal: pendingMeal,
    errorMsg: mealError,
    startPolling,
    handleConfirm: confirmMeal,
    handleCancel: cancelMeal,
  } = useMealConfirmation({
    onConfirmed: (data) => {
      console.log("Meal confirmed:", data);
    },
    onCancelled: (logId) => {
      console.log("Meal cancelled:", logId);
    },
  });

  // Ref to track pending meal trigger count (to detect new messages)
  const mealTriggerRef = useRef(0);
  const prevMessageCountRef = useRef(0);

  // Start polling when chat is open
  useEffect(() => {
    if (isOpen) {
      startPolling(mealTriggerRef.current);
    }
  }, [isOpen, startPolling]);

  // Trigger polling after new message is sent
  useEffect(() => {
    if (messages.length > prevMessageCountRef.current) {
      // New message was sent
      prevMessageCountRef.current = messages.length;
      mealTriggerRef.current += 1;
      // Wait for AI response + extraction, then poll
      setTimeout(() => {
        startPolling(mealTriggerRef.current);
      }, 5000);
    }
  }, [messages.length, startPolling]);

  const handleSend = () => {
    if (inputValue.trim()) {
      sendMessageStream(inputValue, depth);
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
        onDepthChange={setDepth}
        depth={depth}
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
        pendingProposals={pendingProposals}
        proposalLoading={proposalLoading}
        onConfirmProposal={confirmProposal}
        onRejectProposal={rejectProposal}
        // Meal confirmation
        pendingMeal={pendingMeal}
        mealPhase={mealPhase}
        mealError={mealError}
        onConfirmMeal={confirmMeal}
        onCancelMeal={cancelMeal}
      />
    </>
  );
}
