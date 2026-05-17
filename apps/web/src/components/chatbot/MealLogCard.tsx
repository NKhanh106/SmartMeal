"use client";

import { useState } from "react";
import { Pencil, Trash2, X, Check, Utensils } from "lucide-react";

export interface MealLogCardData {
  id: string;
  meal_type: string;
  meal_time: string;
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  source: "manual" | "chat_extraction" | "chat_command";
  items: Array<{
    id: string;
    detected_food_name: string;
    display_food_name?: string;
    estimated_weight_g?: number;
    calories: number;
    protein_g: number;
    carb_g: number;
    fat_g: number;
  }>;
  onEdit?: (id: string, updates: Partial<MealLogCardData>) => void;
  onRemove?: (id: string) => void;
}

interface MealLogCardProps {
  meal: MealLogCardData;
  onEdit?: (id: string, updates: Partial<MealLogCardData>) => void;
  onRemove?: (id: string) => void;
}

const MEAL_TYPE_LABELS: Record<string, string> = {
  bua_sang: "Bữa sáng",
  bua_trua: "Bữa trưa",
  bua_toi: "Bữa tối",
  an_vat: "Ăn vặt",
  khac: "Khác",
};

const MEAL_TYPE_ICONS: Record<string, string> = {
  bua_sang: "🌅",
  bua_trua: "☀️",
  bua_toi: "🌙",
  an_vat: "🍿",
  khac: "🍽️",
};

export function MealLogCard({ meal, onEdit, onRemove }: MealLogCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedFood, setEditedFood] = useState(
    meal.items[0]?.detected_food_name || ""
  );

  const primaryItem = meal.items[0];
  const foodName = primaryItem?.display_food_name || primaryItem?.detected_food_name || "Món ăn";
  const calories = Math.round(primaryItem?.calories || meal.total_calories);

  const handleSave = () => {
    if (onEdit && editedFood.trim()) {
      onEdit(meal.id, {
        items: meal.items.map((item, idx) =>
          idx === 0 ? { ...item, display_food_name: editedFood.trim() } : item
        ),
      });
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditedFood(primaryItem?.detected_food_name || "");
    setIsEditing(false);
  };

  const handleRemove = () => {
    if (onRemove && confirm("Bạn có chắc muốn xóa món ăn này?")) {
      onRemove(meal.id);
    }
  };

  const isFromChat = meal.source === "chat_extraction" || meal.source === "chat_command";
  const sourceLabel = meal.source === "chat_extraction" ? "Trích xuất từ chat" : meal.source === "chat_command" ? "Ghi nhận từ chat" : "Thủ công";

  return (
    <div className="bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{MEAL_TYPE_ICONS[meal.meal_type] || "🍽️"}</span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-amber-800">
                Đã ghi nhận
              </span>
              {isFromChat && (
                <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full">
                  AI Chat
                </span>
              )}
            </div>
            <span className="text-xs text-amber-600">
              {MEAL_TYPE_LABELS[meal.meal_type] || meal.meal_type}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          {onEdit && (
            <>
              {isEditing ? (
                <>
                  <button
                    onClick={handleSave}
                    className="p-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white transition-colors"
                    title="Lưu"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleCancel}
                    className="p-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-600 transition-colors"
                    title="Hủy"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setIsEditing(true)}
                  className="p-1.5 rounded-lg hover:bg-amber-100 text-amber-600 transition-colors"
                  title="Sửa"
                >
                  <Pencil className="w-4 h-4" />
                </button>
              )}
            </>
          )}
          {onRemove && (
            <button
              onClick={handleRemove}
              className="p-1.5 rounded-lg hover:bg-red-100 text-red-500 transition-colors"
              title="Xóa"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Food Name */}
      <div className="mb-3">
        {isEditing ? (
          <input
            type="text"
            value={editedFood}
            onChange={(e) => setEditedFood(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-amber-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
            placeholder="Tên món ăn"
            autoFocus
          />
        ) : (
          <h4 className="text-base font-semibold text-slate-800 flex items-center gap-2">
            <Utensils className="w-4 h-4 text-amber-600" />
            {foodName}
          </h4>
        )}
      </div>

      {/* Nutrition Info */}
      <div className="grid grid-cols-4 gap-2 text-center mb-3">
        <div className="bg-white/60 rounded-lg p-2">
          <p className="text-xs text-slate-500 font-medium">Calories</p>
          <p className="text-sm font-bold text-slate-800">{calories}</p>
        </div>
        <div className="bg-white/60 rounded-lg p-2">
          <p className="text-xs text-slate-500 font-medium">Protein</p>
          <p className="text-sm font-bold text-slate-800">
            {Math.round(primaryItem?.protein_g || 0)}g
          </p>
        </div>
        <div className="bg-white/60 rounded-lg p-2">
          <p className="text-xs text-slate-500 font-medium">Carbs</p>
          <p className="text-sm font-bold text-slate-800">
            {Math.round(primaryItem?.carb_g || 0)}g
          </p>
        </div>
        <div className="bg-white/60 rounded-lg p-2">
          <p className="text-xs text-slate-500 font-medium">Fat</p>
          <p className="text-sm font-bold text-slate-800">
            {Math.round(primaryItem?.fat_g || 0)}g
          </p>
        </div>
      </div>

      {/* Footer */}
      {primaryItem?.estimated_weight_g && (
        <p className="text-xs text-slate-500">
          Khẩu phần: ~{Math.round(primaryItem.estimated_weight_g)}g
        </p>
      )}
    </div>
  );
}
