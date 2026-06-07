"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { DepthMode } from "./DepthSelector";

interface DepthLoadingIndicatorProps {
  mode: DepthMode;
  isVisible: boolean;
}

const LOADING_STATES: Record<DepthMode, { steps: string[]; dotColor: string }> = {
  quick: {
    steps: ["Đang tìm câu trả lời..."],
    dotColor: "bg-amber-400",
  },
  deep: {
    steps: [
      "Đang phân tích tình trạng sức khỏe...",
      "Đang tư vấn dinh dưỡng...",
      "Đang tổng hợp...",
    ],
    dotColor: "bg-emerald-400",
  },
  expert: {
    steps: [
      "Đang kiểm tra sức khỏe toàn diện...",
      "Đang tư vấn dinh dưỡng chuyên sâu...",
      "Đang lên kế hoạch vận động...",
      "Đang tổng hợp khuyến nghị...",
    ],
    dotColor: "bg-violet-400",
  },
};

const STEP_INTERVALS: Record<DepthMode, number> = {
  quick: 1500,
  deep: 2000,
  expert: 2500,
};

export function DepthLoadingIndicator({ mode, isVisible }: DepthLoadingIndicatorProps) {
  const config = LOADING_STATES[mode];
  const intervalMs = STEP_INTERVALS[mode];
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (config.steps.length <= 1) return;
    const timer = setInterval(() => {
      setStepIndex((i) => (i + 1) % config.steps.length);
    }, intervalMs);
    return () => clearInterval(timer);
  }, [config.steps, intervalMs]);

  useEffect(() => {
    setStepIndex(0);
  }, [mode]);

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          className="flex items-center gap-2 px-4 py-2"
        >
          {/* Animated dots */}
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className={`h-1.5 w-1.5 rounded-full ${config.dotColor}`}
                animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }}
                transition={{
                  duration: 1.2,
                  repeat: Infinity,
                  delay: i * 0.2,
                }}
              />
            ))}
          </div>

          {/* Cycling status text */}
          <AnimatePresence mode="wait">
            <motion.span
              key={`${mode}-${stepIndex}`}
              initial={{ opacity: 0, x: 4 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -4 }}
              transition={{ duration: 0.2 }}
              className={`text-xs ${
                mode === "quick"
                  ? "text-amber-600"
                  : mode === "deep"
                  ? "text-emerald-600"
                  : "text-violet-600"
              }`}
            >
              {config.steps[stepIndex]}
            </motion.span>
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
