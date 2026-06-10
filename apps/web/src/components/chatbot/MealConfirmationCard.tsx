"use client";

import { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UtensilsCrossed, Minus, Plus, Loader2, CheckCircle2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ExtractedFoodItem {
  food_name: string;
  quantity: number;
  unit: string;
  calories: number;
  protein_g: number;
  carb_g: number;
  fat_g: number;
}

export interface ExtractedData {
  items: ExtractedFoodItem[];
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  confidence: "high" | "medium" | "low";
  session_id?: string;
}

export interface MealConfirmationCardData {
  id: string;
  user_id: string;
  meal_type: string;
  meal_time: string;
  source: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  extracted_data: ExtractedData;
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  ai_model: string | null;
  ai_confidence: number | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

interface MealConfirmationCardProps {
  data: MealConfirmationCardData;
  onConfirm: (logId: string, finalData: ExtractedData) => Promise<void>;
  onCancel: (logId: string) => void;
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

const MEAL_TYPE_MAP: Record<string, string> = {
  bua_sang: "Bữa sáng",
  bua_trua: "Bữa trưa",
  bua_toi: "Bữa tối",
  an_vat: "Ăn vặt",
  khac: "Khác",
};

const MEAL_TYPE_EMOJI: Record<string, string> = {
  bua_sang: "🌅",
  bua_trua: "☀️",
  bua_toi: "🌙",
  an_vat: "🍿",
  khac: "🍽️",
};

const CONFIDENCE_LABEL: Record<string, { label: string; color: string }> = {
  high:   { label: "Độ chính xác cao",  color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  medium: { label: "Có thể cần chỉnh",  color: "bg-amber-50 text-amber-700 border-amber-200" },
  low:    { label: "Cần xác nhận kỹ",   color: "bg-red-50 text-red-700 border-red-200" },
};

// ─── Skeleton Component ───────────────────────────────────────────────────────

function MealCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.08)] border border-slate-100 overflow-hidden">
      {/* Header skeleton */}
      <div className="px-5 pt-5 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-3 mb-3">
          <Skeleton className="h-10 w-10 rounded-xl" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-52" />
            <Skeleton className="h-3 w-32" />
          </div>
        </div>
      </div>

      {/* Food items skeleton */}
      <div className="px-5 py-4 space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-3 w-24" />
            </div>
            <div className="flex items-center gap-3">
              <Skeleton className="h-8 w-8 rounded-full" />
              <Skeleton className="h-5 w-6" />
              <Skeleton className="h-8 w-8 rounded-full" />
            </div>
          </div>
        ))}
      </div>

      {/* Macros skeleton */}
      <div className="px-5 pb-5">
        <div className="grid grid-cols-4 gap-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      </div>

      {/* Shimmer text */}
      <div className="px-5 pb-5 flex items-center gap-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
        <Skeleton className="h-3 w-64" />
      </div>
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

export function MealConfirmationCard({
  data,
  onConfirm,
  onCancel,
}: MealConfirmationCardProps) {
  const [items, setItems] = useState<ExtractedFoodItem[]>(() => [
    ...(data.extracted_data?.items ?? []),
  ]);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset items if data changes (e.g., polling found new record)
  useEffect(() => {
    setItems([...(data.extracted_data?.items ?? [])]);
    setError(null);
  }, [data.id, data.extracted_data]);

  // ── Computed macros ─────────────────────────────────────────────────────────
  const macros = useMemo(() => {
    const totalCal  = items.reduce((s, i) => s + i.calories * i.quantity, 0);
    const totalProt = items.reduce((s, i) => s + i.protein_g * i.quantity, 0);
    const totalCarb = items.reduce((s, i) => s + i.carb_g  * i.quantity, 0);
    const totalFat  = items.reduce((s, i) => s + i.fat_g   * i.quantity, 0);
    return {
      calories: Math.round(totalCal),
      protein_g: Math.round(totalProt * 10) / 10,
      carb_g:    Math.round(totalCarb * 10) / 10,
      fat_g:     Math.round(totalFat  * 10) / 10,
    };
  }, [items]);

  // ── Quantity stepper ────────────────────────────────────────────────────────
  const adjustQty = (index: number, delta: -1 | 1) => {
    setItems((prev) => {
      const updated = [...prev];
      const nextQty = Math.max(0, updated[index].quantity + delta);
      updated[index] = { ...updated[index], quantity: nextQty };
      return updated;
    });
  };

  // ── Submit ───────────────────────────────────────────────────────────────────
  const handleConfirm = async () => {
    setIsConfirming(true);
    setError(null);
    try {
      const finalData: ExtractedData = {
        ...data.extracted_data,
        items,
        total_calories: macros.calories,
        total_protein_g: macros.protein_g,
        total_carb_g: macros.carb_g,
        total_fat_g: macros.fat_g,
      };
      await onConfirm(data.id, finalData);
      setIsConfirmed(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Xác nhận thất bại. Vui lòng thử lại."
      );
    } finally {
      setIsConfirming(false);
    }
  };

  const mealLabel = MEAL_TYPE_MAP[data.meal_type] ?? data.meal_type;
  const mealEmoji = MEAL_TYPE_EMOJI[data.meal_type] ?? "🍽️";
  const confidence = CONFIDENCE_LABEL[data.extracted_data?.confidence ?? "medium"];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.97 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="bg-white rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.08)] border border-slate-200 overflow-hidden w-full max-w-md"
    >
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="px-5 pt-5 pb-4 border-b border-slate-100 bg-gradient-to-r from-emerald-50/60 to-white">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-11 w-11 rounded-xl bg-emerald-500/10 border border-emerald-200
                            flex items-center justify-center flex-shrink-0">
              <UtensilsCrossed className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 text-sm leading-snug">
                Xác nhận nhật ký ăn uống
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {mealEmoji} {mealLabel}
              </p>
            </div>
          </div>

          <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
            <span
              className={cn(
                "text-xs px-2 py-0.5 rounded-full border font-medium",
                confidence.color
              )}
            >
              {confidence.label}
            </span>
          </div>
        </div>
      </div>

      {/* ── Food Items List ─────────────────────────────────────────────────── */}
      <div className="px-5 py-4 divide-y divide-slate-100">
        <AnimatePresence initial={false}>
          {items.map((item, idx) => (
            <motion.div
              key={`${item.food_name}-${idx}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.04 }}
              className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
            >
              {/* Food info */}
              <div className="flex-1 min-w-0 mr-3">
                <p className="text-sm font-medium text-slate-800 truncate leading-snug">
                  {item.food_name}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {item.calories} kcal · {item.protein_g}p / {item.carb_g}c / {item.fat_g}f
                  {item.unit && ` · ${item.unit}`}
                </p>
              </div>

              {/* Quantity stepper */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={() => adjustQty(idx, -1)}
                  disabled={isConfirming || isConfirmed}
                  aria-label="Giảm số lượng"
                  className={cn(
                    "h-8 w-8 rounded-full border border-slate-200",
                    "flex items-center justify-center",
                    "text-slate-500 hover:border-red-300 hover:text-red-500 hover:bg-red-50",
                    "active:scale-90 transition-all duration-150",
                    "disabled:opacity-40 disabled:cursor-not-allowed",
                    "disabled:hover:border-slate-200 disabled:hover:text-slate-500 disabled:hover:bg-transparent"
                  )}
                >
                  <Minus className="h-3.5 w-3.5" />
                </button>

                <span className="w-7 text-center text-sm font-semibold text-slate-800 tabular-nums">
                  {item.quantity}
                </span>

                <button
                  onClick={() => adjustQty(idx, 1)}
                  disabled={isConfirming || isConfirmed}
                  aria-label="Tăng số lượng"
                  className={cn(
                    "h-8 w-8 rounded-full border border-slate-200",
                    "flex items-center justify-center",
                    "text-slate-500 hover:border-emerald-300 hover:text-emerald-600 hover:bg-emerald-50",
                    "active:scale-90 transition-all duration-150",
                    "disabled:opacity-40 disabled:cursor-not-allowed",
                    "disabled:hover:border-slate-200 disabled:hover:text-slate-500 disabled:hover:bg-transparent"
                  )}
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* ── Macros Grid ─────────────────────────────────────────────────────── */}
      <div className="px-5 pb-4">
        <div className="grid grid-cols-4 gap-2">
          <MacroChip
            label="Calories"
            value={macros.calories}
            unit="kcal"
            accent="orange"
          />
          <MacroChip
            label="Protein"
            value={macros.protein_g}
            unit="g"
            accent="blue"
          />
          <MacroChip
            label="Carbs"
            value={macros.carb_g}
            unit="g"
            accent="amber"
          />
          <MacroChip
            label="Fat"
            value={macros.fat_g}
            unit="g"
            accent="purple"
          />
        </div>
      </div>

      {/* ── Error Banner ────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="px-5 pb-3"
          >
            <div className="text-xs text-red-600 bg-red-50 border border-red-200
                            rounded-lg px-3 py-2">
              {error}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Bottom Actions ──────────────────────────────────────────────────── */}
      <div className="px-5 pb-5 flex gap-2.5">
        <Button
          onClick={handleConfirm}
          disabled={isConfirming || isConfirmed}
          className="flex-1 h-10 rounded-xl font-semibold text-sm
                     bg-emerald-500 text-white shadow-md shadow-emerald-500/20
                     hover:bg-emerald-600 active:bg-emerald-700
                     disabled:opacity-60 disabled:cursor-not-allowed
                     transition-all duration-150"
        >
          {isConfirming ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Đang lưu…
            </>
          ) : isConfirmed ? (
            <>
              <CheckCircle2 className="h-4 w-4" />
              Đã xác nhận
            </>
          ) : (
            "✓ Xác nhận lưu"
          )}
        </Button>

        <Button
          variant="outline"
          onClick={() => onCancel(data.id)}
          disabled={isConfirming || isConfirmed}
          className="h-10 px-4 rounded-xl font-medium text-sm
                     text-slate-500 border border-slate-200
                     hover:bg-slate-50 hover:border-slate-300 hover:text-slate-700
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-all duration-150"
        >
          <X className="h-4 w-4" />
          Hủy
        </Button>
      </div>
    </motion.div>
  );
}

// ─── MacroChip Sub-component ───────────────────────────────────────────────────

interface MacroChipProps {
  label: string;
  value: number;
  unit: string;
  accent: "orange" | "blue" | "amber" | "purple";
}

const MACRO_STYLES: Record<MacroChipProps["accent"], { bg: string; text: string; label: string }> = {
  orange:  { bg: "bg-orange-50",  text: "text-orange-600",  label: "text-orange-400" },
  blue:    { bg: "bg-blue-50",    text: "text-blue-600",    label: "text-blue-400" },
  amber:   { bg: "bg-amber-50",   text: "text-amber-600",   label: "text-amber-400" },
  purple:  { bg: "bg-purple-50",  text: "text-purple-600",  label: "text-purple-400" },
};

function MacroChip({ label, value, unit, accent }: MacroChipProps) {
  const styles = MACRO_STYLES[accent];
  return (
    <div className={cn("rounded-xl px-2 py-2 text-center", styles.bg)}>
      <p className={cn("text-[10px] font-medium uppercase tracking-wide", styles.label)}>
        {label}
      </p>
      <p className={cn("text-sm font-bold mt-0.5", styles.text)}>
        {value}
      </p>
      <p className="text-[10px] text-slate-400">{unit}</p>
    </div>
  );
}
