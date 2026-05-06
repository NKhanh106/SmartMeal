"use client";

import React, { useState, useRef, useCallback } from "react";
import Image from "next/image";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Camera, CheckCircle2, Loader2, Sparkles, AlertCircle, X } from "lucide-react";
import { mealService } from "@/services/meal.service";
import imageCompression from "browser-image-compression";
import type {
  MealUpdatePreviewResponse,
  MealUpdatePreviewItem,
  MealUpdateConfirmItem,
} from "@/lib/types/api";
import { useToast } from "@/hooks/use-toast";

// ─── Constants ─────────────────────────────────────────────────────────────────

const MAX_FILE_SIZE_MB = 10;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

const MEAL_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "bua_sang", label: "Breakfast (Bữa sáng)" },
  { value: "bua_trua", label: "Lunch (Bữa trưa)" },
  { value: "bua_toi", label: "Dinner (Bữa tối)" },
  { value: "an_vat", label: "Snack (Ăn vặt)" },
  { value: "khac", label: "Other (Khác)" },
];

// ─── Types ─────────────────────────────────────────────────────────────────────

interface EditableItem extends MealUpdatePreviewItem {
  editingName: string;
  editingWeight: string;
  editingCalories: string;
  editingProtein: string;
  editingCarbs: string;
  editingFat: string;
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function fileToEditableItem(item: MealUpdatePreviewItem): EditableItem {
  return {
    ...item,
    editingName: item.detected_food_name,
    editingWeight: String(Math.round(item.estimated_weight_g)),
    editingCalories: item.calories != null ? String(Math.round(item.calories)) : "",
    editingProtein: item.protein_g != null ? String(Math.round(item.protein_g)) : "",
    editingCarbs: item.carb_g != null ? String(Math.round(item.carb_g)) : "",
    editingFat: item.fat_g != null ? String(Math.round(item.fat_g)) : "",
  };
}

function editableItemToConfirmItem(item: EditableItem): MealUpdateConfirmItem {
  return {
    food_nutrition_id: item.matched_food_id ?? undefined,
    detected_food_name: item.editingName.trim() || item.detected_food_name,
    estimated_weight_g: Number(item.editingWeight) || item.estimated_weight_g,
    confidence: item.confidence,
  };
}

function validateFile(file: File | null): string | null {
  if (!file) return "No file selected.";
  if (!ALLOWED_TYPES.includes(file.type)) {
    return `Invalid file type. Allowed: JPG, PNG, WebP.`;
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `File too large. Maximum size is ${MAX_FILE_SIZE_MB} MB.`;
  }
  return null;
}

async function compressImage(file: File): Promise<File> {
  // Only compress if > 500KB (avoid recompressing already-small images)
  if (file.size <= 500 * 1024) {
    return file;
  }
  try {
    const compressed = await imageCompression(file, {
      maxSizeMB: 1,
      maxWidthOrHeight: 1024,
      useWebWorker: true,
      fileType: "image/jpeg",
    });
    console.log(
      `[SmartMeal] Compressed: ${(file.size / 1024 / 1024).toFixed(2)} MB → ${(compressed.size / 1024 / 1024).toFixed(2)} MB`
    );
    return compressed;
  } catch (err) {
    console.warn("[SmartMeal] Image compression failed, using original:", err);
    return file;
  }
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function UploadPage() {
  const router = useRouter();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── State ──────────────────────────────────────────────────────────────────
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [mealType, setMealType] = useState("bua_sang");
  const [fileError, setFileError] = useState<string | null>(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const [analysisResult, setAnalysisResult] = useState<MealUpdatePreviewResponse | null>(null);
  const [editableItems, setEditableItems] = useState<EditableItem[]>([]);

  const [confirming, setConfirming] = useState(false);
  const [confirmSuccess, setConfirmSuccess] = useState(false);
  const [savedMealLogId, setSavedMealLogId] = useState<string | null>(null);

  // ── File selection ──────────────────────────────────────────────────────────
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    const error = validateFile(file);
    setFileError(error);
    if (file && !error) {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      const url = URL.createObjectURL(file);
      setSelectedFile(file);
      setPreviewUrl(url);
    } else {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setSelectedFile(null);
      setPreviewUrl(null);
    }
    // Reset analysis state
    setAnalysisResult(null);
    setEditableItems([]);
    setAnalyzeError(null);
    setConfirmSuccess(false);
    setSavedMealLogId(null);
  }, [previewUrl]);

  const handleClearImage = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setSelectedFile(null);
    setPreviewUrl(null);
    setFileError(null);
    setAnalysisResult(null);
    setEditableItems([]);
    setAnalyzeError(null);
    setConfirmSuccess(false);
    setSavedMealLogId(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [previewUrl]);

  // ── Analysis ────────────────────────────────────────────────────────────────
  const handleAnalyze = async () => {
    if (!selectedFile) return;
    setAnalyzing(true);
    setAnalyzeError(null);
    setAnalysisResult(null);
    setEditableItems([]);
    setConfirmSuccess(false);
    setSavedMealLogId(null);
    try {
      // Compress image before upload to reduce bandwidth and prevent timeouts
      const fileToUpload = await compressImage(selectedFile);
      const result = await mealService.analyzeMealImage(fileToUpload, mealType);
      setAnalysisResult(result);
      setEditableItems(result.items.map(fileToEditableItem));
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : "Analysis failed. Please try again.");
    } finally {
      setAnalyzing(false);
    }
  };

  // ── Edit item ──────────────────────────────────────────────────────────────
  const handleItemChange = (
    index: number,
    field: keyof EditableItem,
    value: string
  ) => {
    setEditableItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  };

  // ── Confirm / Save ─────────────────────────────────────────────────────────
  const handleConfirm = async () => {
    if (!analysisResult || editableItems.length === 0) return;
    setConfirming(true);
    try {
      const confirmItems = editableItems.map(editableItemToConfirmItem);
      const result = await mealService.confirmMeal({
        meal_type: mealType,
        items: confirmItems,
      });
      setSavedMealLogId(result.meal_log_id);
      setConfirmSuccess(true);
      toast({ title: "Meal saved successfully!", description: `Logged as ${MEAL_TYPE_OPTIONS.find(o => o.value === mealType)?.label}` });
    } catch (err) {
      toast({
        title: "Failed to save meal.",
        description: err instanceof Error ? err.message : "Please try again.",
        variant: "destructive",
      });
    } finally {
      setConfirming(false);
    }
  };

  // ── Computed totals ────────────────────────────────────────────────────────
  const totalCalories = editableItems.reduce(
    (s, i) => s + (parseFloat(i.editingCalories) || 0), 0
  );
  const totalProtein = editableItems.reduce(
    (s, i) => s + (parseFloat(i.editingProtein) || 0), 0
  );
  const totalCarbs = editableItems.reduce(
    (s, i) => s + (parseFloat(i.editingCarbs) || 0), 0
  );
  const totalFat = editableItems.reduce(
    (s, i) => s + (parseFloat(i.editingFat) || 0), 0
  );

  const canAnalyze = !analyzing && !analysisResult && selectedFile && !fileError;
  const canConfirm = !confirming && analysisResult && editableItems.length > 0 && !confirmSuccess;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-8 max-w-2xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold">Upload Meal</h1>
        <p className="text-muted-foreground">Take a photo of your food to get instant nutritional data.</p>
      </div>

      {/* ── Image Upload Card ─────────────────────────────────────────────── */}
      <Card className="relative overflow-hidden border-2 border-dashed border-primary/20">
        <CardContent className="p-12 flex flex-col items-center justify-center min-h-[300px]">
          {previewUrl ? (
            <div className="relative w-full aspect-video rounded-xl overflow-hidden shadow-lg">
              <Image
                src={previewUrl}
                alt="Meal"
                fill
                className="object-cover"
                unoptimized
              />
              <Button
                variant="destructive"
                size="sm"
                className="absolute top-2 right-2 rounded-full h-8 w-8 p-0"
                onClick={handleClearImage}
                title="Remove image"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="text-center space-y-4">
              <div className="h-16 w-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <Camera className="h-8 w-8 text-primary" />
              </div>
              <div className="space-y-1">
                <p className="font-semibold text-lg">Drop your image here</p>
                <p className="text-sm text-muted-foreground">
                  Supports JPG, PNG, WebP up to {MAX_FILE_SIZE_MB}MB
                </p>
              </div>
              <Label htmlFor="file-upload" className="cursor-pointer">
                <div className="bg-primary hover:bg-primary/90 text-primary-foreground px-6 py-2 rounded-lg font-medium inline-block transition-colors">
                  Select File
                </div>
                <input
                  ref={fileInputRef}
                  id="file-upload"
                  type="file"
                  className="hidden"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleFileChange}
                />
              </Label>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── File Error ───────────────────────────────────────────────────── */}
      <AnimatePresence>
        {fileError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            {fileError}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Meal Type Selector ────────────────────────────────────────────── */}
      <div className="space-y-2">
        <Label htmlFor="meal-type">Meal Type</Label>
        <select
          id="meal-type"
          className="w-full p-2 rounded-md border bg-background"
          value={mealType}
          onChange={(e) => setMealType(e.target.value)}
          disabled={analyzing || !!analysisResult}
        >
          {MEAL_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* ── Analyze Button ────────────────────────────────────────────────── */}
      <Button
        className="w-full h-12 text-lg shadow-lg"
        disabled={!canAnalyze}
        onClick={handleAnalyze}
      >
        {analyzing ? (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Analyzing Ingredients...
          </>
        ) : analysisResult ? (
          <>
            <CheckCircle2 className="mr-2 h-5 w-5" />
            Analysis Complete
          </>
        ) : (
          <>
            <Sparkles className="mr-2 h-5 w-5" />
            AI Analyze Meal
          </>
        )}
      </Button>

      {/* ── Analysis Error ────────────────────────────────────────────────── */}
      <AnimatePresence>
        {analyzeError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="flex items-start gap-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3"
          >
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Analysis failed</p>
              <p className="text-red-600 mt-0.5">{analyzeError}</p>
              <Button
                size="sm"
                variant="link"
                className="text-red-700 p-0 h-auto mt-1"
                onClick={() => setAnalyzeError(null)}
              >
                Dismiss
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── AI Results ────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {analysisResult && !confirmSuccess && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
          >
            <Card className="border-primary/30 bg-white shadow-md overflow-hidden">
              <CardHeader className="bg-slate-50 border-b">
                <CardTitle>AI Recognition Result</CardTitle>
                <CardDescription>
                  Detected components in your image.
                  {analysisResult.overall_confidence != null && (
                    <span className="ml-2 text-green-600 font-medium">
                      Confidence: {Math.round(analysisResult.overall_confidence * 100)}%
                    </span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="p-6 space-y-5">
                {/* Summary Cards */}
                <div className="grid grid-cols-4 gap-4 text-center">
                  <div className="bg-white p-3 rounded-lg border">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Calories</p>
                    <p className="text-lg font-bold">{Math.round(totalCalories)}</p>
                  </div>
                  <div className="bg-white p-3 rounded-lg border">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Protein</p>
                    <p className="text-lg font-bold">{Math.round(totalProtein)}g</p>
                  </div>
                  <div className="bg-white p-3 rounded-lg border">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Carbs</p>
                    <p className="text-lg font-bold">{Math.round(totalCarbs)}g</p>
                  </div>
                  <div className="bg-white p-3 rounded-lg border">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Fat</p>
                    <p className="text-lg font-bold">{Math.round(totalFat)}g</p>
                  </div>
                </div>

                {/* Detected Items List */}
                <div className="space-y-3">
                  <p className="font-semibold text-sm">Detected Items (tap to edit):</p>
                  {editableItems.length === 0 ? (
                    <p className="text-sm text-muted-foreground italic">
                      No items detected. You can still save an empty log if needed.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {editableItems.map((item, idx) => (
                        <EditableItemRow
                          key={idx}
                          item={item}
                          index={idx}
                          onChange={handleItemChange}
                        />
                      ))}
                    </ul>
                  )}
                </div>

                {/* Confirm Button */}
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={handleConfirm}
                  disabled={confirming}
                >
                  {confirming ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Confirm & Add to History"
                  )}
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Confirm Success ────────────────────────────────────────────────── */}
      <AnimatePresence>
        {confirmSuccess && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
          >
            <Card className="border-green-200 bg-green-50">
              <CardContent className="p-8 text-center space-y-4">
                <div className="flex justify-center">
                  <div className="h-16 w-16 bg-green-100 rounded-full flex items-center justify-center">
                    <CheckCircle2 className="h-8 w-8 text-green-600" />
                  </div>
                </div>
                <div>
                  <p className="text-lg font-bold text-green-800">Meal logged successfully!</p>
                  <p className="text-sm text-green-700 mt-1">
                    {Math.round(totalCalories)} kcal saved to your meal history.
                  </p>
                </div>
                <div className="flex gap-3 justify-center">
                  <Button
                    variant="outline"
                    onClick={handleClearImage}
                  >
                    Upload Another
                  </Button>
                  <Button onClick={() => router.push("/history")}>
                    View History
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Editable Item Row ──────────────────────────────────────────────────────────

function EditableItemRow({
  item,
  index,
  onChange,
}: {
  item: EditableItem;
  index: number;
  onChange: (index: number, field: keyof EditableItem, value: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const nutritionValue = [
    item.calories != null ? `${Math.round(item.calories)} kcal` : null,
    item.protein_g != null ? `${Math.round(item.protein_g)}g P` : null,
    item.carb_g != null ? `${Math.round(item.carb_g)}g C` : null,
    item.fat_g != null ? `${Math.round(item.fat_g)}g F` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <li className="bg-white rounded-lg border overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-50"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-2 min-w-0">
          {/* Match status badge */}
          <span
            className={`shrink-0 text-xs px-1.5 py-0.5 rounded font-medium ${
              item.match_status === "matched"
                ? "bg-green-100 text-green-700"
                : item.match_status === "partial"
                ? "bg-yellow-100 text-yellow-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {item.match_status}
          </span>
          <span className="font-medium text-sm truncate">{item.editingName || item.detected_food_name}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {item.confidence != null && (
            <span className="text-xs text-muted-foreground">
              {Math.round(item.confidence * 100)}%
            </span>
          )}
          <span className="text-sm text-muted-foreground">
            {item.editingCalories || "—"} kcal
          </span>
        </div>
      </div>

      {/* Expanded edit form */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: "auto" }}
            exit={{ height: 0 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 pt-1 border-t bg-gray-50 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-0.5">
                  <Label className="text-xs">Food Name</Label>
                  <Input
                    size="sm"
                    value={item.editingName}
                    onChange={(e) => onChange(index, "editingName", e.target.value)}
                  />
                </div>
                <div className="space-y-0.5">
                  <Label className="text-xs">Weight (g)</Label>
                  <Input
                    size="sm"
                    type="number"
                    min={1}
                    value={Number(item.editingWeight) || 0}
                    onChange={(e) => onChange(index, "editingWeight", e.target.value)}
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground font-medium">Nutrition (editable):</p>
              <div className="grid grid-cols-4 gap-2">
                <div className="space-y-0.5">
                  <Label className="text-xs">Cal (kcal)</Label>
                  <Input
                    size="sm"
                    type="number"
                    min={0}
                    value={Number(item.editingCalories) || 0}
                    onChange={(e) => onChange(index, "editingCalories", e.target.value)}
                  />
                </div>
                <div className="space-y-0.5">
                  <Label className="text-xs">Protein (g)</Label>
                  <Input
                    size="sm"
                    type="number"
                    min={0}
                    value={Number(item.editingProtein) || 0}
                    onChange={(e) => onChange(index, "editingProtein", e.target.value)}
                  />
                </div>
                <div className="space-y-0.5">
                  <Label className="text-xs">Carbs (g)</Label>
                  <Input
                    size="sm"
                    type="number"
                    min={0}
                    value={Number(item.editingCarbs) || 0}
                    onChange={(e) => onChange(index, "editingCarbs", e.target.value)}
                  />
                </div>
                <div className="space-y-0.5">
                  <Label className="text-xs">Fat (g)</Label>
                  <Input
                    size="sm"
                    type="number"
                    min={0}
                    value={Number(item.editingFat) || 0}
                    onChange={(e) => onChange(index, "editingFat", e.target.value)}
                  />
                </div>
              </div>
              {nutritionValue && (
                <p className="text-xs text-muted-foreground">
                  AI estimates: {nutritionValue}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}
