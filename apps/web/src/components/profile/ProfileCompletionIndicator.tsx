"use client";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ProfileCompletionIndicatorProps {
  completion: number;
  profile?: Record<string, unknown>;
}

export function ProfileCompletionIndicator({
  completion,
  profile = {},
}: ProfileCompletionIndicatorProps) {
  const missingFields: string[] = [];

  if (!profile.date_of_birth && !profile.height_cm && !profile.age_years && !profile.age) missingFields.push("Thông tin cơ bản");
  if (!profile.usage_goal) missingFields.push("Mục tiêu sử dụng");
  if (!profile.health_conditions && !profile.allergies && !profile.medications) {
    missingFields.push("Tình trạng sức khỏe");
  }
  if (!profile.sleep_duration_hours && !profile.meal_frequency) {
    missingFields.push("Lối sống");
  }
  if (!profile.cuisine_preferences) missingFields.push("Khẩu vị");

  const color =
    completion >= 80
      ? "text-emerald-500"
      : completion >= 50
      ? "text-amber-500"
      : "text-red-400";

  const bgColor =
    completion >= 80
      ? "bg-emerald-500"
      : completion >= 50
      ? "bg-amber-500"
      : "bg-red-400";

  const circumference = 2 * Math.PI * 18;
  const offset = circumference - (completion / 100) * circumference;

  return (
    <Card className="p-4">
      <div className="flex items-center gap-4">
        {/* Ring */}
        <div className="relative shrink-0">
          <svg width="44" height="44" className="-rotate-90">
            <circle cx="22" cy="22" r="18" fill="none" stroke="#e5e7eb" strokeWidth="4" />
            <circle
              cx="22"
              cy="22"
              r="18"
              fill="none"
              className={cn("transition-all duration-500", bgColor)}
              strokeWidth="4"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
            />
          </svg>
          <span className={cn("absolute inset-0 flex items-center justify-center text-xs font-bold", color)}>
            {completion}%
          </span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground">
            Hồ sơ{" "}
            <span className={cn("font-bold", color)}>{completion}%</span>{" "}
            hoàn thiện
          </p>
          {missingFields.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 mt-1">
              {missingFields.map((f) => (
                <span
                  key={f}
                  className="inline-block px-2 py-0.5 bg-amber-50 border border-amber-200 rounded-full text-[11px] text-amber-700 font-medium"
                >
                  Thiếu: {f}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-emerald-600 font-medium mt-0.5">✓ Hồ sơ đã hoàn thiện!</p>
          )}
        </div>

        {/* CTA */}
        {completion < 100 && (
          <a
            href="#wizard"
            className="shrink-0 text-xs font-medium text-emerald-600 hover:text-emerald-700 underline-offset-2 hover:underline"
          >
            Hoàn thiện →
          </a>
        )}
      </div>
    </Card>
  );
}
