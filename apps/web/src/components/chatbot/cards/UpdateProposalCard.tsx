"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, X, ChevronDown, ChevronUp } from "lucide-react";
import type { UpdateProposal } from "@/types/update-proposal";

interface UpdateProposalCardProps {
  proposal: UpdateProposal;
  onConfirm: (proposalId: string) => void;
  onReject: (proposalId: string) => void;
  isLoading?: boolean;
}

const TARGET_ICONS: Record<string, string> = {
  meal_log: "🍽️",
  body_weight: "⚖️",
  body_measurement: "📏",
  health_symptom: "🌡️",
  health_recovery: "💪",
  workout_log: "🏋️",
  muscle_soreness: "💢",
  profile_metric: "👤",
  sleep_log: "😴",
  nutrition_goal: "🎯",
};

const TARGET_COLORS: Record<string, {
  border: string;
  bg: string;
  badge: string;
  button: string;
  buttonHover: string;
}> = {
  meal_log: {
    border: "border-orange-200",
    bg: "bg-orange-50",
    badge: "bg-orange-100 text-orange-700",
    button: "bg-orange-500",
    buttonHover: "hover:bg-orange-600",
  },
  body_weight: {
    border: "border-blue-200",
    bg: "bg-blue-50",
    badge: "bg-blue-100 text-blue-700",
    button: "bg-blue-500",
    buttonHover: "hover:bg-blue-600",
  },
  body_measurement: {
    border: "border-purple-200",
    bg: "bg-purple-50",
    badge: "bg-purple-100 text-purple-700",
    button: "bg-purple-500",
    buttonHover: "hover:bg-purple-600",
  },
  health_symptom: {
    border: "border-red-200",
    bg: "bg-red-50",
    badge: "bg-red-100 text-red-700",
    button: "bg-red-500",
    buttonHover: "hover:bg-red-600",
  },
  health_recovery: {
    border: "border-green-200",
    bg: "bg-green-50",
    badge: "bg-green-100 text-green-700",
    button: "bg-green-500",
    buttonHover: "hover:bg-green-600",
  },
  workout_log: {
    border: "border-emerald-200",
    bg: "bg-emerald-50",
    badge: "bg-emerald-100 text-emerald-700",
    button: "bg-emerald-500",
    buttonHover: "hover:bg-emerald-600",
  },
  muscle_soreness: {
    border: "border-yellow-200",
    bg: "bg-yellow-50",
    badge: "bg-yellow-100 text-yellow-700",
    button: "bg-yellow-500",
    buttonHover: "hover:bg-yellow-600",
  },
  sleep_log: {
    border: "border-indigo-200",
    bg: "bg-indigo-50",
    badge: "bg-indigo-100 text-indigo-700",
    button: "bg-indigo-500",
    buttonHover: "hover:bg-indigo-600",
  },
  nutrition_goal: {
    border: "border-teal-200",
    bg: "bg-teal-50",
    badge: "bg-teal-100 text-teal-700",
    button: "bg-teal-500",
    buttonHover: "hover:bg-teal-600",
  },
};

const DEFAULT_COLORS = {
  border: "border-gray-200",
  bg: "bg-gray-50",
  badge: "bg-gray-100 text-gray-700",
  button: "bg-gray-600",
  buttonHover: "hover:bg-gray-700",
};

export function UpdateProposalCard({
  proposal,
  onConfirm,
  onReject,
  isLoading,
}: UpdateProposalCardProps) {
  const [showDetail, setShowDetail] = useState(false);
  const colors = TARGET_COLORS[proposal.target] ?? DEFAULT_COLORS;
  const icon = TARGET_ICONS[proposal.target] ?? "📝";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={`
        rounded-2xl border-2 ${colors.border} ${colors.bg}
        p-3 shadow-sm mx-1 my-1
      `}
    >
      {/* Header */}
      <div className="flex items-start gap-2.5">
        <span className="text-xl mt-0.5">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800 leading-tight">
            {proposal.summary}
          </p>
          <p className="text-xs text-gray-500 mt-0.5 truncate">
            {proposal.detail}
          </p>
        </div>

        {/* Confidence badge */}
        <span
          className={`
            text-[10px] font-medium px-1.5 py-0.5 rounded-full
            flex-shrink-0 ${colors.badge}
          `}
        >
          {Math.round(proposal.confidence * 100)}%
        </span>
      </div>

      {/* Fields detail (expandable) */}
      {proposal.fields.length > 1 && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setShowDetail(!showDetail)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
          >
            {showDetail ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {showDetail ? "Ẩn chi tiết" : "Xem chi tiết"}
          </button>

          <AnimatePresence>
            {showDetail && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="mt-2 space-y-1">
                  {proposal.fields.map((field, i) => (
                    <div key={i} className="flex justify-between text-xs">
                      <span className="text-gray-500">{field.label}</span>
                      <span className="font-medium text-gray-700">
                        {field.display}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 mt-3">
        <button
          type="button"
          onClick={() => onConfirm(proposal.proposal_id)}
          disabled={isLoading}
          className={`
            flex-1 flex items-center justify-center gap-1.5
            py-1.5 rounded-lg text-xs font-semibold text-white
            transition-all ${colors.button} ${colors.buttonHover}
            disabled:opacity-50 disabled:cursor-not-allowed
            active:scale-95
          `}
        >
          <Check size={13} />
          Lưu lại
        </button>
        <button
          type="button"
          onClick={() => onReject(proposal.proposal_id)}
          disabled={isLoading}
          className="
            flex items-center justify-center gap-1.5
            px-4 py-1.5 rounded-lg text-xs font-medium
            text-gray-500 hover:text-gray-700
            bg-white border border-gray-200 hover:border-gray-300
            transition-all disabled:opacity-50 active:scale-95
          "
        >
          <X size={13} />
          Bỏ qua
        </button>
      </div>
    </motion.div>
  );
}
