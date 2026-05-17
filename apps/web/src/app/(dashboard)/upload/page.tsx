"use client";

import React, { useState, useCallback, memo } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, Loader2, CheckCircle2, Utensils } from "lucide-react";
import { mealService } from "@/services/meal.service";
import { useToast } from "@/hooks/use-toast";
import type { MealType } from "@/lib/types/api";

// ─── Constants ─────────────────────────────────────────────────────────────────

const MEAL_TYPE_OPTIONS: { value: MealType; label: string }[] = [
  { value: "bua_sang", label: "Bữa sáng (Breakfast)" },
  { value: "bua_trua", label: "Bữa trưa (Lunch)" },
  { value: "bua_toi", label: "Bữa tối (Dinner)" },
  { value: "an_vat", label: "Ăn vặt (Snack)" },
  { value: "khac", label: "Khác (Other)" },
];

// ─── Types ─────────────────────────────────────────────────────────────────────

interface FoodItem {
  id: string;
  name: string;
  calories: string;
  protein: string;
  carbs: string;
  fat: string;
  weight: string;
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function createEmptyItem(): FoodItem {
  return {
    id: `item-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    name: "",
    calories: "",
    protein: "",
    carbs: "",
    fat: "",
    weight: "100",
  };
}

function calculateTotals(items: FoodItem[]) {
  return items.reduce(
    (acc, item) => ({
      calories: acc.calories + (parseFloat(item.calories) || 0),
      protein: acc.protein + (parseFloat(item.protein) || 0),
      carbs: acc.carbs + (parseFloat(item.carbs) || 0),
      fat: acc.fat + (parseFloat(item.fat) || 0),
    }),
    { calories: 0, protein: 0, carbs: 0, fat: 0 }
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function UploadPage() {
  const router = useRouter();
  const { toast } = useToast();

  // ── State ──────────────────────────────────────────────────────────────────
  const [mealType, setMealType] = useState<MealType>("bua_trua");
  const [items, setItems] = useState<FoodItem[]>([createEmptyItem()]);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // ── Handlers ────────────────────────────────────────────────────────────────
  const handleAddItem = useCallback(() => {
    setItems((prev) => [...prev, createEmptyItem()]);
  }, []);

  const handleRemoveItem = useCallback((id: string) => {
    setItems((prev) => {
      if (prev.length === 1) return prev; // Keep at least one item
      return prev.filter((item) => item.id !== id);
    });
  }, []);

  const handleItemChange = useCallback(
    (id: string, field: keyof FoodItem, value: string) => {
      setItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, [field]: value } : item))
      );
    },
    []
  );

  const handleSave = async () => {
    // Validate items
    const validItems = items.filter((item) => item.name.trim());
    if (validItems.length === 0) {
      toast({
        title: "Vui lòng nhập ít nhất một món ăn",
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      // Create meal log items
      const mealItems = validItems.map((item) => ({
        detected_food_name: item.name.trim(),
        estimated_weight_g: parseFloat(item.weight) || 100,
        source: "nhap_thu_cong" as const,
        confidence: 1.0,
      }));

      await mealService.createMealLog({
        meal_type: mealType,
        items: mealItems,
      });

      setSaveSuccess(true);
      toast({ title: "Ghi nhận bữa ăn thành công!" });

      // Reset after success
      setTimeout(() => {
        setItems([createEmptyItem()]);
        setSaveSuccess(false);
      }, 3000);
    } catch (err) {
      toast({
        title: "Lưu thất bại",
        description: err instanceof Error ? err.message : "Vui lòng thử lại.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  // ── Computed ──────────────────────────────────────────────────────────────
  const totals = calculateTotals(items);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-8 max-w-2xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold">Ghi nhận bữa ăn</h1>
        <p className="text-muted-foreground">
          Nhập thông tin bữa ăn của bạn một cách thủ công.
        </p>
      </div>

      {/* Success State */}
      {saveSuccess ? (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="p-8 text-center space-y-4">
            <div className="flex justify-center">
              <div className="h-16 w-16 bg-green-100 rounded-full flex items-center justify-center">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
            </div>
            <div>
              <p className="text-lg font-bold text-green-800">Đã ghi nhận bữa ăn!</p>
              <p className="text-sm text-green-700 mt-1">
                Tổng: {Math.round(totals.calories)} kcal
              </p>
            </div>
            <div className="flex gap-3 justify-center">
              <Button variant="outline" onClick={() => setItems([createEmptyItem()])}>
                Thêm bữa khác
              </Button>
              <Button onClick={() => router.push("/history")}>
                Xem lịch sử
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Meal Type Selector */}
          <Card className="border-slate-200">
            <CardHeader>
              <CardTitle>Loại bữa ăn</CardTitle>
              <CardDescription>Chọn loại bữa ăn bạn muốn ghi nhận</CardDescription>
            </CardHeader>
            <CardContent>
              <select
                className="w-full p-3 rounded-lg border bg-background text-sm"
                value={mealType}
                onChange={(e) => setMealType(e.target.value as MealType)}
              >
                {MEAL_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </CardContent>
          </Card>

          {/* Food Items */}
          <Card className="border-slate-200">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Các món ăn</CardTitle>
                  <CardDescription>Thêm các món bạn đã ăn</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={handleAddItem} className="gap-2">
                  <Plus className="h-4 w-4" />
                  Thêm món
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {items.map((item, index) => (
                <FoodItemRow
                  key={item.id}
                  item={item}
                  index={index}
                  onChange={handleItemChange}
                  onRemove={handleRemoveItem}
                  canRemove={items.length > 1}
                />
              ))}

              {/* Totals */}
              <div className="pt-4 border-t">
                <div className="grid grid-cols-4 gap-4 text-center">
                  <div className="bg-slate-50 p-3 rounded-lg">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Calories</p>
                    <p className="text-lg font-bold">{Math.round(totals.calories)}</p>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-lg">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Protein</p>
                    <p className="text-lg font-bold">{Math.round(totals.protein)}g</p>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-lg">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Carbs</p>
                    <p className="text-lg font-bold">{Math.round(totals.carbs)}g</p>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-lg">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Fat</p>
                    <p className="text-lg font-bold">{Math.round(totals.fat)}g</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <Button
            className="w-full h-12 text-lg shadow-lg"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? (
              <>
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Đang lưu...
              </>
            ) : (
              <>
                <Utensils className="mr-2 h-5 w-5" />
                Lưu bữa ăn
              </>
            )}
          </Button>
        </>
      )}

      {/* Chat tip */}
      <div className="text-center text-sm text-muted-foreground">
        <p>
          💡 Bạn cũng có thể ghi nhận bữa ăn nhanh chóng qua chatbot bằng cách nhắn tin như:
        </p>
        <p className="font-medium mt-1">
          &ldquo;Tôi vừa ăn phở&rdquo; hoặc &ldquo;Log cơm gà&rdquo;
        </p>
      </div>
    </div>
  );
}

// ─── Food Item Row ─────────────────────────────────────────────────────────────

const FoodItemRow = memo(function FoodItemRow({
  item,
  index,
  onChange,
  onRemove,
  canRemove,
}: {
  item: FoodItem;
  index: number;
  onChange: (id: string, field: keyof FoodItem, value: string) => void;
  onRemove: (id: string) => void;
  canRemove: boolean;
}) {
  return (
    <div className="flex gap-3 items-start p-4 bg-slate-50/50 rounded-xl">
      <div className="flex-1 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Tên món</Label>
            <Input
              placeholder="Ví dụ: Cơm gà xối mỡ"
              value={item.name}
              onChange={(e) => onChange(item.id, "name", e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Khối lượng (g)</Label>
            <Input
              type="number"
              placeholder="100"
              value={item.weight}
              onChange={(e) => onChange(item.id, "weight", e.target.value)}
            />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Calories</Label>
            <Input
              type="number"
              placeholder="0"
              value={item.calories}
              onChange={(e) => onChange(item.id, "calories", e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Protein (g)</Label>
            <Input
              type="number"
              placeholder="0"
              value={item.protein}
              onChange={(e) => onChange(item.id, "protein", e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Carbs (g)</Label>
            <Input
              type="number"
              placeholder="0"
              value={item.carbs}
              onChange={(e) => onChange(item.id, "carbs", e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Fat (g)</Label>
            <Input
              type="number"
              placeholder="0"
              value={item.fat}
              onChange={(e) => onChange(item.id, "fat", e.target.value)}
            />
          </div>
        </div>
      </div>
      {canRemove && (
        <button
          onClick={() => onRemove(item.id)}
          className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          title="Xóa món"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      )}
    </div>
  );
});
