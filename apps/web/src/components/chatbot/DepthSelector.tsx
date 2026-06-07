"use client";

import { useState } from "react";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

export type DepthMode = "quick" | "deep" | "expert";

interface DepthOption {
  value: DepthMode;
  icon: string;
  label: string;
  sublabel: string;
  time: string;
  activeBg: string;
  activeColor: string;
  activeBorder: string;
  activeShadow: string;
}

const DEPTH_OPTIONS: DepthOption[] = [
  {
    value: "quick",
    icon: "⚡",
    label: "Nhanh",
    sublabel: "Trả lời cơ bản",
    time: "~2 giây",
    activeBg: "bg-amber-50",
    activeColor: "text-amber-600",
    activeBorder: "border-amber-300",
    activeShadow: "shadow-amber-200",
  },
  {
    value: "deep",
    icon: "🔍",
    label: "Sâu hơn",
    sublabel: "Có phân tích",
    time: "~5 giây",
    activeBg: "bg-emerald-50",
    activeColor: "text-emerald-600",
    activeBorder: "border-emerald-300",
    activeShadow: "shadow-emerald-200",
  },
  {
    value: "expert",
    icon: "🧠",
    label: "Chuyên gia",
    sublabel: "Tư vấn toàn diện",
    time: "~10 giây",
    activeBg: "bg-violet-50",
    activeColor: "text-violet-600",
    activeBorder: "border-violet-300",
    activeShadow: "shadow-violet-200",
  },
];

interface DepthSelectorProps {
  value: DepthMode;
  onChange: (mode: DepthMode) => void;
  disabled?: boolean;
}

export function DepthSelector({ value, onChange, disabled }: DepthSelectorProps) {
  return (
    <TooltipProvider>
      <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-0.5">
        {DEPTH_OPTIONS.map((option) => {
          const isActive = value === option.value;

          return (
            <Tooltip key={option.value}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => !disabled && onChange(option.value)}
                  disabled={disabled}
                  className={`
                    relative flex items-center gap-1.5 rounded-md px-2.5 py-1.5
                    text-xs font-medium transition-all duration-200
                    ${isActive
                      ? `${option.activeBg} ${option.activeColor} border ${option.activeBorder} shadow-sm ${option.activeShadow}`
                      : "text-slate-500 border border-transparent hover:bg-white hover:text-slate-700"
                    }
                    ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}
                  `}
                  aria-pressed={isActive}
                  aria-label={`${option.label}: ${option.sublabel}`}
                >
                  <span className="text-sm leading-none">{option.icon}</span>
                  <span className="hidden sm:inline">{option.label}</span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-[180px]">
                <div className="text-center">
                  <p className="font-semibold">
                    <span className="mr-1">{option.icon}</span>
                    {option.label}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {option.sublabel}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    <span className="mr-0.5">⏱</span>
                    {option.time}
                  </p>
                </div>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
