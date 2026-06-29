"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Menu } from "lucide-react";
import { ChatHeader } from "./ChatHeader";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";
import { ChatSessionSidebar } from "./ChatSessionSidebar";
import { ChatCardContainer, UpdateProposalCard } from "./cards";
import { MealConfirmationCard } from "./MealConfirmationCard";
import type { ChatMessage, ChatSession, StaleSessionWarning, MealLogCardData } from "./types";
import type { ChatCard, ChatCardResponse } from "./types";
import type { DepthMode } from "./DepthSelector";
import type { UpdateProposal } from "@/types/update-proposal";
import type { MealConfirmationCardData } from "./MealConfirmationCard";

interface ChatPanelProps {
  isOpen: boolean;
  messages: ChatMessage[];
  mealLogs?: MealLogCardData[];
  inputValue: string;
  isTyping: boolean;
  isLoading: boolean;
  currentSession: ChatSession | null;
  sessions: ChatSession[];
  staleWarning: StaleSessionWarning | null;
  showSidebar: boolean;
  pendingCard: ChatCard | null;
  isCardLoading: boolean;
  depth: DepthMode;
  // Proposal state
  pendingProposals: UpdateProposal[];
  proposalLoading: string | null;
  onConfirmProposal: (proposalId: string) => void;
  onRejectProposal: (proposalId: string) => void;
  // Meal confirmation state
  pendingMeal: MealConfirmationCardData | null;
  mealPhase: "idle" | "loading" | "has_data" | "confirming" | "confirmed" | "error";
  mealError: string | null;
  onConfirmMeal: (logId: string, finalData: import("./MealConfirmationCard").ExtractedData) => Promise<void>;
  onCancelMeal: (logId: string) => void;
  // Handlers
  onInputChange: (value: string) => void;
  onSend: () => void;
  onDepthChange: (depth: DepthMode) => void;
  onMinimize: () => void;
  onToggleSidebar: () => void;
  onSelectSession: (session: ChatSession) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onDismissStale: () => void;
  onStartNewChat: () => void;
  onEditMealLog?: (id: string, updates: Partial<MealLogCardData>) => void;
  onRemoveMealLog?: (id: string) => void;
  onRetry?: () => void;
  onSubmitCard: (response: ChatCardResponse) => void;
  onSkipCard: () => void;
}

export function ChatPanel({
  isOpen,
  messages,
  mealLogs = [],
  inputValue,
  isTyping,
  isLoading,
  currentSession,
  sessions,
  staleWarning,
  showSidebar,
  pendingCard,
  isCardLoading,
  depth,
  pendingProposals,
  proposalLoading,
  onConfirmProposal,
  onRejectProposal,
  pendingMeal,
  mealPhase,
  mealError,
  onConfirmMeal,
  onCancelMeal,
  onInputChange,
  onSend,
  onDepthChange,
  onMinimize,
  onToggleSidebar,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  onDismissStale,
  onStartNewChat,
  onEditMealLog,
  onRemoveMealLog,
  onRetry,
  onSubmitCard,
  onSkipCard,
}: ChatPanelProps) {
  const inputDisabled = pendingCard !== null && !pendingCard.skippable;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20, transformOrigin: "bottom right" }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="fixed bottom-24 right-6 z-[100] flex bg-white rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.2)] overflow-hidden"
          style={{ width: "min(90vw, 800px)", height: "min(70vh, 700px)" }}
        >
          {/* Sidebar */}
          <AnimatePresence>
            {showSidebar && (
              <motion.div
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 288, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="border-r border-slate-200"
              >
                <ChatSessionSidebar
                  sessions={sessions}
                  currentSessionId={currentSession?.id || null}
                  isLoading={isLoading}
                  onSelectSession={onSelectSession}
                  onNewChat={onNewChat}
                  onDeleteSession={onDeleteSession}
                  onRenameSession={onRenameSession}
                  onClose={onToggleSidebar}
                />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Main Chat Area */}
          <div className="flex flex-col flex-1 min-w-0">
            {/* Top Bar */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 bg-white">
              <button
                onClick={onToggleSidebar}
                className={`p-2 rounded-xl transition-colors ${
                  showSidebar
                    ? "bg-emerald-100 text-emerald-600"
                    : "hover:bg-slate-100 text-slate-500"
                }`}
                title="Danh sách cuộc trò chuyện"
              >
                <Menu className="w-5 h-5" />
              </button>
            </div>

            {/* Header */}
            <ChatHeader
              onMinimize={onMinimize}
              session={currentSession}
              staleWarning={staleWarning}
              onRenameSession={onRenameSession}
              onDismissStale={onDismissStale}
              onStartNewChat={onStartNewChat}
            />

            {/* Messages */}
            <ChatMessageList
              messages={messages}
              mealLogs={mealLogs}
              isTyping={isTyping}
              depth={depth}
              onEditMealLog={onEditMealLog}
              onRemoveMealLog={onRemoveMealLog}
              onRetry={onRetry}
            />

            {/* Stale Session Warning Banner — blocks input until dismissed */}
            {staleWarning && (
              <div className="mx-4 mb-1 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                <div className="flex items-start gap-3">
                  <span className="text-amber-500 text-lg mt-0.5">⚠️</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-amber-800">
                      Đây là cuộc trò chuyện cũ
                    </p>
                    <p className="text-xs text-amber-700 mt-0.5">
                      {staleWarning.days_since_activity
                        ? `${staleWarning.days_since_activity} ngày trước`
                        : "Hơn 24 giờ trước"}{" "}
                      — Tiếp tục ở đây hay bắt đầu cuộc trò chuyện mới?
                    </p>
                    <div className="flex gap-2 mt-2">
                      <button
                        type="button"
                        onClick={onDismissStale}
                        className="text-xs px-3 py-1 bg-amber-100 hover:bg-amber-200 text-amber-800 rounded-md transition-colors"
                      >
                        Tiếp tục
                      </button>
                      <button
                        type="button"
                        onClick={onStartNewChat}
                        className="text-xs px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-md transition-colors"
                      >
                        Cuộc trò chuyện mới
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Interactive Card (floats between messages and input) */}
            <AnimatePresence>
              {pendingCard && (
                <div className="px-1 pb-1">
                  <ChatCardContainer
                    card={pendingCard}
                    onSubmit={onSubmitCard}
                    onSkip={onSkipCard}
                    isLoading={isCardLoading}
                  />
                </div>
              )}
            </AnimatePresence>

            {/* Update Proposals (appear above input, below messages) */}
            <AnimatePresence>
              {pendingProposals.map((proposal) => (
                <UpdateProposalCard
                  key={proposal.proposal_id}
                  proposal={proposal}
                  onConfirm={onConfirmProposal}
                  onReject={onRejectProposal}
                  isLoading={proposalLoading === proposal.proposal_id}
                />
              ))}
            </AnimatePresence>

            {/* Meal Confirmation Card */}
            <AnimatePresence>
              {pendingMeal && mealPhase !== "idle" && mealPhase !== "loading" && (
                <div className="px-1 pb-1">
                  <MealConfirmationCard
                    data={pendingMeal}
                    onConfirm={onConfirmMeal}
                    onCancel={onCancelMeal}
                  />
                </div>
              )}
            </AnimatePresence>

            {/* Input */}
            <ChatInput
              value={inputValue}
              depth={depth}
              onChange={onInputChange}
              onDepthChange={onDepthChange}
              onSend={onSend}
              disabled={isTyping || inputDisabled}
              placeholder={
                pendingCard
                  ? "Vui lòng trả lời câu hỏi trên..."
                  : undefined
              }
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
