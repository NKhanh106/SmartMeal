"""
Reference constants for health conditions, allergens, dietary restrictions, and cuisines.
Used for validation and UI rendering across the app.
"""

HEALTH_CONDITIONS = [
    # Metabolic
    {"id": "type2_diabetes", "label": "Tiểu đường type 2", "category": "metabolic", "dietary_impact": "high"},
    {"id": "type1_diabetes", "label": "Tiểu đường type 1", "category": "metabolic", "dietary_impact": "high"},
    {"id": "prediabetes", "label": "Tiền tiểu đường", "category": "metabolic", "dietary_impact": "high"},
    {"id": "obesity", "label": "Béo phì", "category": "metabolic", "dietary_impact": "high"},
    {"id": "metabolic_syndrome", "label": "Hội chứng chuyển hóa", "category": "metabolic", "dietary_impact": "high"},
    {"id": "thyroid_hypo", "label": "Suy giáp", "category": "metabolic", "dietary_impact": "medium"},
    {"id": "thyroid_hyper", "label": "Cường giáp", "category": "metabolic", "dietary_impact": "medium"},
    {"id": "gout", "label": "Gout (tăng acid uric)", "category": "metabolic", "dietary_impact": "high"},
    # Cardiovascular
    {"id": "hypertension", "label": "Tăng huyết áp", "category": "cardiovascular", "dietary_impact": "high"},
    {"id": "hyperlipidemia", "label": "Rối loạn lipid máu", "category": "cardiovascular", "dietary_impact": "high"},
    {"id": "heart_disease", "label": "Bệnh tim mạch", "category": "cardiovascular", "dietary_impact": "high"},
    {"id": "stroke_history", "label": "Tiền sử đột quỵ", "category": "cardiovascular", "dietary_impact": "high"},
    # Digestive
    {"id": "ibs", "label": "Hội chứng ruột kích thích (IBS)", "category": "digestive", "dietary_impact": "high"},
    {"id": "acid_reflux", "label": "Trào ngược dạ dày (GERD)", "category": "digestive", "dietary_impact": "high"},
    {"id": "gastric_ulcer", "label": "Loét dạ dày", "category": "digestive", "dietary_impact": "high"},
    {"id": "ibd", "label": "Viêm ruột mãn tính (IBD/Crohn)", "category": "digestive", "dietary_impact": "high"},
    {"id": "fatty_liver", "label": "Gan nhiễm mỡ", "category": "digestive", "dietary_impact": "high"},
    {"id": "liver_disease", "label": "Bệnh gan mãn tính", "category": "digestive", "dietary_impact": "high"},
    {"id": "kidney_disease", "label": "Bệnh thận mãn tính (CKD)", "category": "digestive", "dietary_impact": "high"},
    {"id": "kidney_stones", "label": "Sỏi thận", "category": "digestive", "dietary_impact": "high"},
    # Musculoskeletal
    {"id": "osteoporosis", "label": "Loãng xương", "category": "musculoskeletal", "dietary_impact": "medium"},
    {"id": "rheumatoid_arthritis", "label": "Viêm khớp dạng thấp", "category": "musculoskeletal", "dietary_impact": "medium"},
    {"id": "osteoarthritis", "label": "Thoái hóa khớp", "category": "musculoskeletal", "dietary_impact": "low"},
    # Neurological / Mental
    {"id": "depression", "label": "Trầm cảm", "category": "mental", "dietary_impact": "medium"},
    {"id": "anxiety", "label": "Lo âu mãn tính", "category": "mental", "dietary_impact": "low"},
    {"id": "insomnia", "label": "Mất ngủ mãn tính", "category": "mental", "dietary_impact": "medium"},
    # Hormonal
    {"id": "pcos", "label": "Buồng trứng đa nang (PCOS)", "category": "hormonal", "dietary_impact": "high"},
    {"id": "menopause", "label": "Mãn kinh", "category": "hormonal", "dietary_impact": "medium"},
    {"id": "pregnancy", "label": "Mang thai", "category": "hormonal", "dietary_impact": "high"},
    {"id": "breastfeeding", "label": "Đang cho con bú", "category": "hormonal", "dietary_impact": "high"},
    # Other
    {"id": "anemia", "label": "Thiếu máu / thiếu sắt", "category": "other", "dietary_impact": "high"},
    {"id": "celiac", "label": "Celiac (không dung nạp gluten)", "category": "other", "dietary_impact": "high"},
    {"id": "lactose_intolerance", "label": "Không dung nạp lactose", "category": "other", "dietary_impact": "medium"},
    {"id": "none", "label": "Không có bệnh lý", "category": "none", "dietary_impact": "none"},
]

ALLERGENS = [
    "peanuts",
    "tree_nuts",
    "milk",
    "eggs",
    "wheat",
    "soy",
    "fish",
    "shellfish",
    "sesame",
    "sulfites",
]

DIETARY_RESTRICTIONS = [
    "vegetarian",
    "vegan",
    "pescatarian",
    "halal",
    "kosher",
    "gluten_free",
    "dairy_free",
    "keto",
    "paleo",
    "low_fodmap",
    "low_sodium",
    "low_purine",
    "diabetic_diet",
    "renal_diet",
]

CUISINE_TYPES = [
    "vietnamese",
    "japanese",
    "korean",
    "chinese",
    "thai",
    "mediterranean",
    "western",
    "indian",
    "middle_eastern",
    "fusion",
]

# Maps condition IDs to dietary rule flags returned by get_dietary_rules()
CONDITION_RULES = {
    "type2_diabetes": ["limit_simple_carbs", "prioritize_low_gi", "limit_sugar", "increase_fiber"],
    "type1_diabetes": ["limit_simple_carbs", "prioritize_low_gi", "limit_sugar", "increase_fiber"],
    "prediabetes": ["limit_simple_carbs", "prioritize_low_gi", "limit_sugar"],
    "hypertension": ["limit_sodium_2g_day", "dash_diet", "limit_alcohol"],
    "hyperlipidemia": ["limit_saturated_fat", "limit_cholesterol", "increase_fiber"],
    "heart_disease": ["limit_sodium_2g_day", "limit_saturated_fat", "limit_cholesterol"],
    "stroke_history": ["limit_sodium_2g_day", "limit_saturated_fat"],
    "gout": ["limit_purine", "avoid_organ_meats", "avoid_shellfish", "hydration"],
    "kidney_disease": ["limit_protein_0.8g_kg", "limit_potassium", "limit_phosphorus"],
    "kidney_stones": ["increase_hydration", "limit_oxalate", "limit_sodium"],
    "fatty_liver": ["avoid_alcohol", "limit_saturated_fat", "limit_fructose", "increase_fiber"],
    "ibs": ["low_fodmap", "avoid_trigger_foods", "small_frequent_meals"],
    "acid_reflux": ["avoid_spicy", "avoid_citrus", "small_frequent_meals", "no_late_meals"],
    "gastric_ulcer": ["avoid_spicy", "avoid_acidic", "small_frequent_meals"],
    "osteoporosis": ["increase_calcium", "increase_vitamin_d", "limit_caffeine"],
    "rheumatoid_arthritis": ["anti_inflammatory", "increase_omega3"],
    "pcos": ["low_gi", "limit_refined_carbs", "anti_inflammatory"],
    "pregnancy": ["increase_folate", "increase_iron", "avoid_raw_fish", "limit_caffeine_200mg"],
    "breastfeeding": ["increase_calories_500", "increase_hydration", "increase_protein"],
    "anemia": ["increase_iron", "increase_vitamin_c", "limit_tannin"],
    "celiac": ["strict_gluten_free"],
    "lactose_intolerance": ["dairy_free"],
}

# Maps usage goal to nutrition goal type for automatic goal creation
USAGE_GOAL_TO_NUTRITION_GOAL = {
    "muscle_gain": "tang_co",
    "weight_gain": "tang_co",
    "weight_loss": "giam_can",
    "maintain_shape": "giu_can",
    "balanced_lifestyle": "giu_can",
    "nutrient_supplement": "giu_can",
    "medical_treatment": "giu_can",
    "sports_performance": "tang_co",
    "pregnancy_nursing": "giu_can",
    "elderly_nutrition": "giu_can",
}
