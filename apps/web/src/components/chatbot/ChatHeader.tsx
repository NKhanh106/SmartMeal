"use client";

import { useState } from "react";
import { Minus, Bot, Check, X } from "lucide-react";
import type { ChatSession, StaleSessionWarning } from "./types";

interface ChatHeaderProps {
  onMinimize: () => void;
  session: ChatSession | null;
  staleWarning: StaleSessionWarning | null;
  onRenameSession: (sessionId: string, title: string) => void;
  onDismissStale: () => void;
  onStartNewChat: () => void;
}

export function ChatHeader({
  onMinimize,
  session,
  staleWarning,
  onRenameSession,
  onDismissStale,
  onStartNewChat,
}: ChatHeaderProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");

  const handleStartEdit = () => {
    if (session) {
      setEditTitle(session.title || "");
      setIsEditing(true);
    }
  };

  const handleSave = () => {
    if (session && editTitle.trim()) {
      onRenameSession(session.id, editTitle.trim());
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditTitle("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSave();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  };

  return (
    <div className="flex flex-col">
      {/* Main Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-emerald-500 text-white">
        {/* Left: bot avatar + info */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 bg-white/20 rounded-xl flex items-center justify-center">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            {isEditing ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={handleKeyDown}
                  autoFocus
                  className="px-2 py-1 text-sm bg-white/20 border border-white/30 rounded-lg text-white placeholder-emerald-100 focus:outline-none focus:ring-2 focus:ring-white/50"
                  maxLength={60}
                  placeholder="Tên cuộc trò chuyện"
                />
                <button
                  onClick={handleSave}
                  className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                >
                  <Check className="h-4 w-4" />
                </button>
                <button
                  onClick={handleCancel}
                  className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <>
                <h3
                  className="font-bold text-sm cursor-pointer hover:text-emerald-100 transition-colors"
                  onClick={handleStartEdit}
                  title="Click để đổi tên"
                >
                  {session?.title || "SmartMeal Assistant"}
                </h3>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 bg-emerald-200 rounded-full animate-pulse" />
                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-50">
                    {session ? "Đang trò chuyện" : "Sẵn sàng hỗ trợ"}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right: minimize */}
        <button
          onClick={onMinimize}
          className="flex h-8 w-8 items-center justify-center rounded-full text-white hover:bg-white/20 transition-colors"
          aria-label="Thu nhỏ"
        >
          <Minus className="h-5 w-5" />
        </button>
      </div>

      {/* Stale Warning Banner */}
      {staleWarning?.is_stale && (
        <div className="px-4 py-3 bg-amber-50 border-b border-amber-200">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-amber-700 text-sm">
                Tiếp tục cuộc trò chuyện từ{" "}
                <strong>{staleWarning.days_since_activity} ngày trước</strong>.
                Bắt đầu cuộc trò chuyện mới?
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onDismissStale}
                className="px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100 rounded-lg transition-colors"
              >
                Tiếp tục
              </button>
              <button
                onClick={onStartNewChat}
                className="px-3 py-1.5 text-xs font-medium bg-emerald-500 text-white hover:bg-emerald-600 rounded-lg transition-colors"
              >
                Cuộc trò chuyện mới
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
