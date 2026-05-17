"use client";

import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { vi } from "date-fns/locale";
import { MessageSquare, Plus, Trash2, X, Check } from "lucide-react";
import type { ChatSession } from "./types";

interface ChatSessionSidebarProps {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;
  onSelectSession: (session: ChatSession) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onClose: () => void;
}

export function ChatSessionSidebar({
  sessions,
  currentSessionId,
  isLoading,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  onClose,
}: ChatSessionSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const handleStartEdit = (session: ChatSession) => {
    setEditingId(session.id);
    setEditingTitle(session.title || "Cuộc trò chuyện mới");
  };

  const handleSaveEdit = () => {
    if (editingId && editingTitle.trim()) {
      onRenameSession(editingId, editingTitle.trim());
    }
    setEditingId(null);
    setEditingTitle("");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSaveEdit();
    } else if (e.key === "Escape") {
      handleCancelEdit();
    }
  };

  const formatTime = (dateString: string | null) => {
    if (!dateString) return "";
    try {
      const date = new Date(dateString);
      return formatDistanceToNow(date, { addSuffix: true, locale: vi });
    } catch {
      return "";
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 border-r border-slate-200 w-72">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-slate-600" />
          <span className="font-semibold text-slate-800">Cuộc trò chuyện</span>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-slate-200 transition-colors md:hidden"
          aria-label="Đóng sidebar"
        >
          <X className="w-5 h-5 text-slate-600" />
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Plus className="w-4 h-4" />
          Cuộc trò chuyện mới
        </button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {sessions.length === 0 && !isLoading ? (
          <div className="text-center py-8 text-slate-500 text-sm">
            <MessageSquare className="w-10 h-10 mx-auto mb-2 text-slate-300" />
            <p>Chưa có cuộc trò chuyện nào</p>
            <p className="text-xs mt-1">Bắt đầu một cuộc trò chuyện mới</p>
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`group relative rounded-xl transition-all ${
                  currentSessionId === session.id
                    ? "bg-emerald-100 border border-emerald-200"
                    : "hover:bg-slate-100 border border-transparent"
                }`}
                onMouseEnter={() => setHoveredId(session.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                {editingId === session.id ? (
                  /* Edit Mode */
                  <div className="p-3">
                    <input
                      type="text"
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onKeyDown={handleKeyDown}
                      onBlur={handleSaveEdit}
                      autoFocus
                      className="w-full px-2 py-1.5 text-sm border border-emerald-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                      maxLength={60}
                    />
                    <div className="flex items-center gap-1 mt-2">
                      <button
                        onClick={handleSaveEdit}
                        className="p-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white transition-colors"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={handleCancelEdit}
                        className="p-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-600 transition-colors"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Display Mode */
                  <button
                    onClick={() => onSelectSession(session)}
                    className="w-full text-left p-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">
                          {session.title || "Cuộc trò chuyện mới"}
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {formatTime(session.last_message_at || session.updated_at)}
                        </p>
                      </div>
                    </div>
                  </button>
                )}

                {/* Hover Actions */}
                {hoveredId === session.id && editingId !== session.id && (
                  <div className="absolute top-2 right-2 flex items-center gap-1">
                    <button
                      onClick={() => handleStartEdit(session)}
                      className="p-1.5 rounded-lg bg-white/80 hover:bg-white text-slate-500 hover:text-slate-700 transition-colors shadow-sm"
                      title="Đổi tên"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => onDeleteSession(session.id)}
                      className="p-1.5 rounded-lg bg-white/80 hover:bg-white text-red-500 hover:text-red-600 transition-colors shadow-sm"
                      title="Xóa"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
