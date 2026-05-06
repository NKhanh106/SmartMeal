export interface RecognizedDish {
  name: string;
  name_en: string;
  estimated_weight_g: number;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  confidence: number;
}

export interface FoodRecognitionResult {
  dishes: RecognizedDish[];
  total_calories: number;
  meal_type_suggestion: "breakfast" | "lunch" | "dinner" | "snack";
  notes?: string;
  from_cache: boolean;
}
