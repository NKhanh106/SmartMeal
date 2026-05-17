"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { ProfileCompletionIndicator } from "@/components/profile/ProfileCompletionIndicator";
import { useAuth } from "@/contexts/auth-context";
import { useToast } from "@/hooks/use-toast";
import { profileService } from "@/services/profile.service";
import { authService } from "@/services/auth.service";
import { nutritionGoalService } from "@/services/nutrition-goal.service";
import type {
  UserProfileCreate,
  UserProfileUpdate,
  UserProfileResponse,
  UsageGoal,
  SleepQuality,
  MealFrequency,
  CookingPreference,
  EatingSpeed,
  HealthConditionItem,
  AllergyItem,
  MedicationItem,
  TastePreferencesSchema,
} from "@/lib/types/api";
import { cn } from "@/lib/utils";

const WIZARD_STEPS = [
  { id: 1, label: "Thông tin cơ bản", shortLabel: "Cơ bản" },
  { id: 2, label: "Mục tiêu sử dụng", shortLabel: "Mục tiêu" },
  { id: 3, label: "Tình trạng sức khỏe", shortLabel: "Sức khỏe" },
  { id: 4, label: "Lối sống", shortLabel: "Lối sống" },
  { id: 5, label: "Khẩu vị & ẩm thực", shortLabel: "Khẩu vị" },
];

const STORAGE_KEY = "smartmeal_profile_wizard_state";

const USAGE_GOALS: { value: UsageGoal; label: string; icon: string; description: string }[] = [
  { value: "muscle_gain", label: "Tăng cơ", icon: "💪", description: "Xây dựng cơ bắp, tập gym" },
  { value: "weight_loss", label: "Giảm cân", icon: "⚖️", description: "Giảm mỡ, kiểm soát cân nặng" },
  { value: "weight_gain", label: "Tăng cân", icon: "📈", description: "Tăng cân lành mạnh" },
  { value: "maintain_shape", label: "Giữ dáng", icon: "🏃", description: "Duy trì vóc dáng hiện tại" },
  { value: "nutrient_supplement", label: "Bổ sung chất", icon: "🥗", description: "Bổ sung dinh dưỡng" },
  { value: "medical_treatment", label: "Điều trị bệnh lý", icon: "🏥", description: "Hỗ trợ điều trị theo chỉ định" },
  { value: "balanced_lifestyle", label: "Sinh hoạt điều độ", icon: "🌿", description: "Lối sống cân bằng" },
  { value: "sports_performance", label: "Hiệu suất thể thao", icon: "🏆", description: "Tối ưu thành tích" },
  { value: "pregnancy_nursing", label: "Mang thai / Cho con bú", icon: "🤱", description: "Dinh dưỡng thai kỳ" },
  { value: "elderly_nutrition", label: "Người cao tuổi", icon: "👴", description: "Dinh dưỡng người cao tuổi" },
];

const HEALTH_CONDITIONS_OPTIONS: { id: string; label: string; category: string }[] = [
  { id: "type2_diabetes", label: "Tiểu đường type 2", category: "Chuyển hóa" },
  { id: "type1_diabetes", label: "Tiểu đường type 1", category: "Chuyển hóa" },
  { id: "prediabetes", label: "Tiền tiểu đường", category: "Chuyển hóa" },
  { id: "hypertension", label: "Tăng huyết áp", category: "Tim mạch" },
  { id: "hyperlipidemia", label: "Rối loạn lipid máu", category: "Tim mạch" },
  { id: "heart_disease", label: "Bệnh tim mạch", category: "Tim mạch" },
  { id: "gout", label: "Gout (tăng acid uric)", category: "Chuyển hóa" },
  { id: "ibs", label: "Hội chứng ruột kích thích (IBS)", category: "Tiêu hóa" },
  { id: "acid_reflux", label: "Trào ngược dạ dày (GERD)", category: "Tiêu hóa" },
  { id: "fatty_liver", label: "Gan nhiễm mỡ", category: "Tiêu hóa" },
  { id: "kidney_disease", label: "Bệnh thận mãn tính (CKD)", category: "Tiêu hóa" },
  { id: "osteoporosis", label: "Loãng xương", category: "Xương khớp" },
  { id: "anemia", label: "Thiếu máu / thiếu sắt", category: "Khác" },
  { id: "celiac", label: "Celiac (không dung nạp gluten)", category: "Khác" },
  { id: "lactose_intolerance", label: "Không dung nạp lactose", category: "Khác" },
  { id: "pcos", label: "Buồng trứng đa nang (PCOS)", category: "Nội tiết" },
  { id: "pregnancy", label: "Mang thai", category: "Nội tiết" },
  { id: "breastfeeding", label: "Đang cho con bú", category: "Nội tiết" },
  { id: "depression", label: "Trầm cảm", category: "Tâm thần" },
  { id: "insomnia", label: "Mất ngủ mãn tính", category: "Tâm thần" },
  { id: "none", label: "Không có bệnh lý", category: "Khác" },
];

const ALLERGEN_OPTIONS = [
  "peanuts", "tree_nuts", "milk", "eggs", "wheat", "soy", "fish", "shellfish", "sesame", "sulfites",
];

const ALLERGEN_LABELS: Record<string, string> = {
  peanuts: "Đậu phộng", tree_nuts: "Hạt cây", milk: "Sữa", eggs: "Trứng",
  wheat: "Gluten", soy: "Đậu nành", fish: "Cá", shellfish: "Sò",
  sesame: "Mè", sulfites: "Sunphit",
};

const DIETARY_RESTRICTION_OPTIONS = [
  "vegetarian", "vegan", "pescatarian", "halal", "kosher",
  "gluten_free", "dairy_free", "keto", "paleo", "low_sodium",
];

const DIETARY_LABELS: Record<string, string> = {
  vegetarian: "Ăn chay", vegan: "Thuần chay", pescatarian: "Pescatarian",
  halal: "Halal", kosher: "Kosher", gluten_free: "Không gluten",
  dairy_free: "Không sữa", keto: "Keto", paleo: "Paleo", low_sodium: "Ít muối",
};

const CUISINE_OPTIONS = [
  "vietnamese", "japanese", "korean", "chinese", "thai",
  "mediterranean", "western", "indian", "middle_eastern", "fusion",
];

const CUISINE_LABELS: Record<string, string> = {
  vietnamese: "Việt Nam", japanese: "Nhật Bản", korean: "Hàn Quốc",
  chinese: "Trung Hoa", thai: "Thái Lan", mediterranean: "Địa Trung Hải",
  western: "Phương Tây", indian: "Ấn Độ", middle_eastern: "Trung Đông", fusion: "Fusion",
};

interface WizardFormData {
  // Step 1: Basic
  full_name: string;
  date_of_birth: string;
  gender: string;
  height: number;
  weight: number;
  // Step 2: Usage Goal
  usage_goal: UsageGoal | undefined;
  usage_goal_note: string;
  // Step 3: Health Conditions
  health_conditions: HealthConditionItem[];
  allergies: AllergyItem[];
  medications: MedicationItem[];
  dietary_restrictions: string[];
  // Step 4: Lifestyle
  sleep_duration_hours: number;
  sleep_quality: SleepQuality | undefined;
  sleep_schedule: string;
  stress_level: number;
  meal_frequency: MealFrequency | undefined;
  cooking_preference: CookingPreference | undefined;
  wake_up_time: string;
  sleep_time: string;
  work_schedule: string;
  // Step 5: Taste
  taste_preferences: TastePreferencesSchema;
  cuisine_preferences: string[];
  disliked_foods: string[];
  favorite_foods: string[];
  eating_speed: EatingSpeed | undefined;
  chew_difficulty: boolean;
}

const EMPTY_FORM = (): WizardFormData => ({
  full_name: "", date_of_birth: "", gender: "nam", height: 170, weight: 65,
  usage_goal: undefined, usage_goal_note: "",
  health_conditions: [], allergies: [], medications: [], dietary_restrictions: [],
  sleep_duration_hours: 7, sleep_quality: undefined, sleep_schedule: "",
  stress_level: 5, meal_frequency: undefined, cooking_preference: undefined,
  wake_up_time: "06:00", sleep_time: "22:00", work_schedule: "",
  taste_preferences: { spicy: 3, sweet: 3, salty: 3, sour: 3, bitter: 2 },
  cuisine_preferences: [], disliked_foods: [], favorite_foods: [],
  eating_speed: undefined, chew_difficulty: false,
});

export default function ProfilePage() {
  const { user, updateUser } = useAuth();
  const { toast } = useToast();

  const [step, setStep] = useState(1);
  const [form, setForm] = useState<WizardFormData>(EMPTY_FORM());
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [existingProfile, setExistingProfile] = useState<UserProfileResponse | null>(null);
  const [profileCompletion, setProfileCompletion] = useState(0);
  const didInit = useRef(false);

  // Load saved wizard state or existing profile
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;

    profileService.getMyProfile().then((data) => {
      setExistingProfile(data);
      setForm(apiToForm(data));
      setStep(1);
    }).catch(() => {
      // Try loading from localStorage (incomplete wizard data)
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try { setForm(JSON.parse(saved)); } catch { /* ignore */ }
      }
    }).finally(() => setLoading(false));
  }, []);

  // Persist wizard state to localStorage
  useEffect(() => {
    if (!loading && !existingProfile) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(form));
    }
  }, [form, loading, existingProfile]);

  function apiToForm(api: UserProfileResponse): WizardFormData {
    return {
      full_name: user?.full_name ?? "",
      date_of_birth: api.date_of_birth,
      gender: api.gender === "nam" ? "nam" : api.gender === "nu" ? "nu" : "khac",
      height: Number(api.height_cm),
      weight: Number(api.current_weight_kg),
      usage_goal: api.usage_goal,
      usage_goal_note: api.usage_goal_note || "",
      health_conditions: api.health_conditions || [],
      allergies: api.allergies || [],
      medications: api.medications || [],
      dietary_restrictions: api.dietary_restrictions || [],
      sleep_duration_hours: api.sleep_duration_hours || 7,
      sleep_quality: api.sleep_quality,
      sleep_schedule: api.sleep_schedule || "",
      stress_level: api.stress_level || 5,
      meal_frequency: api.meal_frequency,
      cooking_preference: api.cooking_preference,
      wake_up_time: api.wake_up_time || "06:00",
      sleep_time: api.sleep_time || "22:00",
      work_schedule: api.work_schedule || "",
      taste_preferences: api.taste_preferences || { spicy: 3, sweet: 3, salty: 3, sour: 3, bitter: 2 },
      cuisine_preferences: api.cuisine_preferences || [],
      disliked_foods: api.disliked_foods || [],
      favorite_foods: api.favorite_foods || [],
      eating_speed: api.eating_speed,
      chew_difficulty: api.chew_difficulty || false,
    };
  }

  function formToApi(f: WizardFormData): UserProfileCreate | UserProfileUpdate {
    const base = {
      gender: f.gender as UserProfileCreate["gender"],
      date_of_birth: f.date_of_birth || undefined,
      height_cm: f.height,
      current_weight_kg: f.weight,
    };
    const extended = {
      usage_goal: f.usage_goal,
      usage_goal_note: f.usage_goal_note || undefined,
      health_conditions: f.health_conditions.length > 0 ? f.health_conditions : undefined,
      allergies: f.allergies.length > 0 ? f.allergies : undefined,
      medications: f.medications.length > 0 ? f.medications : undefined,
      dietary_restrictions: f.dietary_restrictions.length > 0 ? f.dietary_restrictions : undefined,
      sleep_duration_hours: f.sleep_duration_hours || undefined,
      sleep_quality: f.sleep_quality,
      sleep_schedule: f.sleep_schedule || undefined,
      stress_level: f.stress_level || undefined,
      meal_frequency: f.meal_frequency,
      cooking_preference: f.cooking_preference,
      wake_up_time: f.wake_up_time || undefined,
      sleep_time: f.sleep_time || undefined,
      work_schedule: f.work_schedule || undefined,
      taste_preferences: f.taste_preferences,
      cuisine_preferences: f.cuisine_preferences.length > 0 ? f.cuisine_preferences : undefined,
      disliked_foods: f.disliked_foods.length > 0 ? f.disliked_foods : undefined,
      favorite_foods: f.favorite_foods.length > 0 ? f.favorite_foods : undefined,
      eating_speed: f.eating_speed,
      chew_difficulty: f.chew_difficulty || undefined,
    };
    return { ...base, ...extended };
  }

  function calculateCompletion(f: WizardFormData): number {
    let score = 0;
    // Basic info: 30%
    if (f.date_of_birth && f.gender && f.height && f.weight) score += 30;
    // Usage goal: 20%
    if (f.usage_goal) score += 20;
    // Health conditions: 20%
    if (f.health_conditions.length > 0 || f.allergies.length > 0) score += 20;
    // Lifestyle: 15%
    if (f.sleep_duration_hours || f.meal_frequency) score += 15;
    // Taste: 15%
    if (f.cuisine_preferences.length > 0) score += 15;
    return score;
  }

  const handleSave = async () => {
    setSubmitting(true);
    try {
      if (form.full_name !== (user?.full_name ?? "")) {
        await authService.updateUser({ full_name: form.full_name || undefined });
        await updateUser({ full_name: form.full_name || undefined });
      }
      const payload = formToApi(form);
      if (existingProfile) {
        await profileService.updateMyProfile(payload as UserProfileUpdate);
        toast({ title: "Hồ sơ đã được cập nhật." });
      } else {
        await profileService.createProfile(payload as UserProfileCreate);
        toast({ title: "Hồ sơ đã được tạo thành công." });
        const created = await profileService.getMyProfile();
        setExistingProfile(created);
      }
      localStorage.removeItem(STORAGE_KEY);
      const completion = calculateCompletion(form);
      setProfileCompletion(completion);
    } catch (err: unknown) {
      const error = err as { getUserMessage?: () => string };
      toast({
        title: "Lưu thất bại.",
        description: error.getUserMessage?.() ?? "Vui lòng thử lại.",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const update = (partial: Partial<WizardFormData>) =>
    setForm((prev) => ({ ...prev, ...partial }));

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold">Hồ sơ sức khỏe</h1>
        <p className="text-muted-foreground">Cập nhật thông tin cá nhân để nhận gợi ý dinh dưỡng phù hợp.</p>
      </div>

      <ProfileCompletionIndicator
        completion={calculateCompletion(form)}
        profile={form as any}
      />

      <WizardProgressBar currentStep={step} totalSteps={5} steps={WIZARD_STEPS} />

      {step === 1 && (
        <StepBasicInfo form={form} update={update} userName={user?.full_name ?? user?.email ?? "User"} />
      )}
      {step === 2 && <StepUsageGoal form={form} update={update} />}
      {step === 3 && <StepHealthConditions form={form} update={update} />}
      {step === 4 && <StepLifestyle form={form} update={update} />}
      {step === 5 && <StepTastePreferences form={form} update={update} />}

      <WizardNavigation
        step={step}
        onBack={() => setStep((s) => Math.max(1, s - 1))}
        onNext={() => setStep((s) => Math.min(5, s + 1))}
        onSave={handleSave}
        isSubmitting={submitting}
        isLastStep={step === 5}
      />
    </div>
  );
}

// ─── Progress Bar ──────────────────────────────────────────────────────────────

function WizardProgressBar({
  currentStep,
  totalSteps,
  steps,
}: {
  currentStep: number;
  totalSteps: number;
  steps: typeof WIZARD_STEPS;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
        <span>Bước {currentStep} / {totalSteps}</span>
        <span>{steps[currentStep - 1]?.label}</span>
      </div>
      <div className="flex gap-1.5">
        {steps.map((s) => (
          <div key={s.id} className="flex-1 flex flex-col items-center gap-1">
            <div
              className={cn(
                "w-full h-1.5 rounded-full transition-all duration-300",
                s.id < currentStep
                  ? "bg-emerald-500"
                  : s.id === currentStep
                  ? "bg-emerald-300"
                  : "bg-slate-100"
              )}
            />
            <span className={cn(
              "text-[10px] hidden sm:block",
              s.id === currentStep ? "text-emerald-600 font-semibold" : "text-muted-foreground"
            )}>
              {s.shortLabel}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Navigation ───────────────────────────────────────────────────────────────

function WizardNavigation({
  step,
  onBack,
  onNext,
  onSave,
  isSubmitting,
  isLastStep,
}: {
  step: number;
  onBack: () => void;
  onNext: () => void;
  onSave: () => void;
  isSubmitting: boolean;
  isLastStep: boolean;
}) {
  return (
    <div className="flex items-center justify-between pt-4 border-t">
      <Button
        variant="outline"
        onClick={onBack}
        disabled={step === 1}
        className="min-w-[100px]"
      >
        ← Quay lại
      </Button>
      <div className="flex gap-2">
        {step < 5 && (
          <Button onClick={onNext} className="min-w-[100px]">
            Tiếp tục →
          </Button>
        )}
        {step === 5 && (
          <Button
            onClick={onSave}
            disabled={isSubmitting}
            className="min-w-[140px] bg-emerald-500 hover:bg-emerald-600"
          >
            {isSubmitting ? "Đang lưu..." : "💾 Lưu hồ sơ"}
          </Button>
        )}
      </div>
    </div>
  );
}

// ─── Step 1: Basic Info ───────────────────────────────────────────────────────

function StepBasicInfo({
  form,
  update,
  userName,
}: {
  form: WizardFormData;
  update: (p: Partial<WizardFormData>) => void;
  userName: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Thông tin cơ bản</CardTitle>
        <CardDescription>Thông tin cá nhân cơ bản để tính chỉ số dinh dưỡng.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="full_name">Họ và tên</Label>
          <Input
            id="full_name"
            type="text"
            placeholder="VD: Nguyễn Văn An"
            value={form.full_name}
            onChange={(e) => update({ full_name: e.target.value })}
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="date_of_birth">Ngày sinh</Label>
            <Input
              id="date_of_birth"
              type="date"
              value={form.date_of_birth}
              onChange={(e) => update({ date_of_birth: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>Giới tính</Label>
            <select
              className="w-full p-2.5 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              value={form.gender}
              onChange={(e) => update({ gender: e.target.value })}
            >
              <option value="nam">Nam</option>
              <option value="nu">Nữ</option>
              <option value="khac">Khác</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label>Chiều cao (cm)</Label>
            <Input
              type="number" min={50} max={250}
              value={form.height}
              onChange={(e) => update({ height: Number(e.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label>Cân nặng (kg)</Label>
            <Input
              type="number" min={20} max={300}
              value={form.weight}
              onChange={(e) => update({ weight: Number(e.target.value) })}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Step 2: Usage Goal ───────────────────────────────────────────────────────

function StepUsageGoal({
  form,
  update,
}: {
  form: WizardFormData;
  update: (p: Partial<WizardFormData>) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Mục tiêu sử dụng SmartMeal</CardTitle>
        <CardDescription>
          Chọn mục tiêu chính của bạn để nhận gợi ý phù hợp nhất.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {USAGE_GOALS.map((goal) => (
            <button
              key={goal.value}
              onClick={() => update({ usage_goal: goal.value })}
              className={cn(
                "flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all text-center",
                form.usage_goal === goal.value
                  ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                  : "border-slate-100 bg-white hover:border-emerald-200 hover:bg-emerald-50/30"
              )}
            >
              <span className="text-3xl">{goal.icon}</span>
              <div>
                <p className="text-sm font-semibold">{goal.label}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{goal.description}</p>
              </div>
              {form.usage_goal === goal.value && (
                <div className="absolute top-2 right-2 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center text-white text-xs">✓</div>
              )}
            </button>
          ))}
        </div>

        {form.usage_goal === "medical_treatment" && (
          <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
            <strong>⚠️ Lưu ý:</strong> Bạn đang chọn mục tiêu điều trị bệnh lý.
            SmartMeal sẽ điều chỉnh gợi ý theo tình trạng sức khỏe của bạn.
            <strong> Luôn tham khảo bác sĩ trước khi thay đổi chế độ ăn.</strong>
          </div>
        )}

        <div className="space-y-2">
          <Label className="text-sm text-muted-foreground">
            Ghi chú thêm về mục tiêu (tùy chọn)
          </Label>
          <textarea
            className="w-full p-3 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
            rows={2}
            placeholder="VD: Tập gym 4 buổi/tuần, muốn giảm 5kg trong 3 tháng..."
            value={form.usage_goal_note}
            onChange={(e) => update({ usage_goal_note: e.target.value })}
          />
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Step 3: Health Conditions ──────────────────────────────────────────────

function StepHealthConditions({
  form,
  update,
}: {
  form: WizardFormData;
  update: (p: Partial<WizardFormData>) => void;
}) {
  const [search, setSearch] = useState("");
  const [medInput, setMedInput] = useState("");
  const [medFreq, setMedFreq] = useState("");

  const grouped = HEALTH_CONDITIONS_OPTIONS.reduce<Record<string, typeof HEALTH_CONDITIONS_OPTIONS>>((acc, c) => {
    if (!acc[c.category]) acc[c.category] = [];
    acc[c.category].push(c);
    return acc;
  }, {});

  const filtered = search
    ? HEALTH_CONDITIONS_OPTIONS.filter((c) =>
        c.label.toLowerCase().includes(search.toLowerCase())
      )
    : null;

  function toggleCondition(id: string) {
    const existing = form.health_conditions.find((c) => c.condition === id);
    if (existing) {
      update({ health_conditions: form.health_conditions.filter((c) => c.condition !== id) });
    } else if (id === "none") {
      update({ health_conditions: [{ condition: "none", severity: "resolved" }] });
    } else {
      update({
        health_conditions: [
          ...form.health_conditions.filter((c) => c.condition !== "none"),
          { condition: id, severity: "managed" },
        ],
      });
    }
  }

  function toggleAllergen(allergen: string) {
    const existing = form.allergies.find((a) => a.allergen === allergen);
    if (existing) {
      update({ allergies: form.allergies.filter((a) => a.allergen !== allergen) });
    } else {
      update({ allergies: [...form.allergies, { allergen, severity: "moderate" }] });
    }
  }

  function toggleDietary(restriction: string) {
    if (form.dietary_restrictions.includes(restriction)) {
      update({ dietary_restrictions: form.dietary_restrictions.filter((r) => r !== restriction) });
    } else {
      update({ dietary_restrictions: [...form.dietary_restrictions, restriction] });
    }
  }

  function addMedication() {
    if (!medInput.trim()) return;
    update({
      medications: [
        ...form.medications,
        { name: medInput.trim(), frequency: medFreq || undefined },
      ],
    });
    setMedInput("");
    setMedFreq("");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tình trạng sức khỏe</CardTitle>
        <CardDescription>
          Thông tin này giúp AI điều chỉnh gợi ý dinh dưỡng phù hợp và an toàn.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">

        {/* Search */}
        <div className="relative">
          <Input
            placeholder="Tìm kiếm bệnh lý..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">🔍</span>
        </div>

        {/* Condition List */}
        {filtered ? (
          <div className="space-y-2">
            {filtered.map((c) => {
              const selected = form.health_conditions.some((hc) => hc.condition === c.id);
              return (
                <button
                  key={c.id}
                  onClick={() => toggleCondition(c.id)}
                  className={cn(
                    "w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all",
                    selected
                      ? "border-emerald-400 bg-emerald-50"
                      : "border-slate-100 hover:border-emerald-200"
                  )}
                >
                  <div className={cn(
                    "w-5 h-5 rounded border-2 flex items-center justify-center transition-all shrink-0",
                    selected ? "bg-emerald-500 border-emerald-500" : "border-slate-300"
                  )}>
                    {selected && <span className="text-white text-xs">✓</span>}
                  </div>
                  <div>
                    <p className="text-sm font-medium">{c.label}</p>
                    <p className="text-xs text-muted-foreground">{c.category}</p>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          Object.entries(grouped).map(([category, conditions]) => (
            <div key={category}>
              <h4 className="text-sm font-semibold text-muted-foreground mb-2 uppercase tracking-wide">{category}</h4>
              <div className="space-y-1.5 mb-4">
                {conditions.map((c) => {
                  const selected = form.health_conditions.some((hc) => hc.condition === c.id);
                  return (
                    <button
                      key={c.id}
                      onClick={() => toggleCondition(c.id)}
                      className={cn(
                        "w-full flex items-center gap-3 p-2.5 rounded-lg border text-left transition-all",
                        selected
                          ? "border-emerald-400 bg-emerald-50"
                          : "border-slate-100 hover:border-emerald-200"
                      )}
                    >
                      <div className={cn(
                        "w-4 h-4 rounded border-2 flex items-center justify-center transition-all shrink-0",
                        selected ? "bg-emerald-500 border-emerald-500" : "border-slate-300"
                      )}>
                        {selected && <span className="text-white text-[10px]">✓</span>}
                      </div>
                      <span className="text-sm">{c.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}

        {/* Per-condition severity cards */}
        {form.health_conditions.length > 0 && form.health_conditions[0].condition !== "none" && (
          <div className="space-y-3">
            <Label className="text-sm">Mức độ kiểm soát (cho từng bệnh lý đã chọn):</Label>
            {form.health_conditions.map((hc) => {
              const conditionInfo = HEALTH_CONDITIONS_OPTIONS.find((c) => c.id === hc.condition);
              return (
                <div key={hc.condition} className="border border-slate-200 rounded-xl p-4 space-y-3 bg-slate-50/50">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{conditionInfo?.label ?? hc.condition}</span>
                    <button
                      onClick={() => toggleCondition(hc.condition)}
                      className="text-red-400 hover:text-red-600 text-xs"
                    >
                      ✕ Bỏ chọn
                    </button>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {(["managed", "unmanaged", "resolved"] as const).map((sev) => (
                      <button
                        key={sev}
                        onClick={() => update({
                          health_conditions: form.health_conditions.map((item) =>
                            item.condition === hc.condition ? { ...item, severity: sev } : item
                          ),
                        })}
                        className={cn(
                          "px-3 py-1.5 rounded-full text-xs font-medium border transition-all",
                          hc.severity === sev
                            ? "bg-emerald-100 border-emerald-400 text-emerald-700"
                            : "border-slate-200 text-muted-foreground hover:border-emerald-200"
                        )}
                      >
                        {sev === "managed" ? "✓ Đang kiểm soát" : sev === "unmanaged" ? "⚠ Chưa điều trị" : "✓ Đã hồi phục"}
                      </button>
                    ))}
                  </div>
                  <textarea
                    className="w-full p-2 rounded-lg border border-slate-200 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
                    rows={2}
                    placeholder="Ghi chú (tùy chọn)"
                    value={hc.note ?? ""}
                    onChange={(e) => update({
                      health_conditions: form.health_conditions.map((item) =>
                        item.condition === hc.condition ? { ...item, note: e.target.value || undefined } : item
                      ),
                    })}
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* Allergies */}
        <div className="space-y-2">
          <Label>Dị ứng thực phẩm</Label>
          <div className="flex flex-wrap gap-2">
            {ALLERGEN_OPTIONS.map((allergen) => {
              const selected = form.allergies.some((a) => a.allergen === allergen);
              return (
                <button
                  key={allergen}
                  onClick={() => toggleAllergen(allergen)}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-xs font-medium border transition-all",
                    selected
                      ? "bg-red-50 border-red-300 text-red-700"
                      : "border-slate-200 text-muted-foreground hover:border-red-200"
                  )}
                >
                  {ALLERGEN_LABELS[allergen] || allergen}
                  {selected && " ✓"}
                </button>
              );
            })}
          </div>
        </div>

        {/* Dietary Restrictions */}
        <div className="space-y-2">
          <Label>Hạn chế ăn uống</Label>
          <div className="flex flex-wrap gap-2">
            {DIETARY_RESTRICTION_OPTIONS.map((restriction) => {
              const selected = form.dietary_restrictions.includes(restriction);
              return (
                <button
                  key={restriction}
                  onClick={() => toggleDietary(restriction)}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-xs font-medium border transition-all",
                    selected
                      ? "bg-amber-50 border-amber-300 text-amber-700"
                      : "border-slate-200 text-muted-foreground hover:border-amber-200"
                  )}
                >
                  {DIETARY_LABELS[restriction] || restriction}
                  {selected && " ✓"}
                </button>
              );
            })}
          </div>
        </div>

        {/* Medications */}
        <div className="space-y-2">
          <Label>Thuốc đang dùng</Label>
          <div className="space-y-2">
            {form.medications.map((med, idx) => (
              <div key={idx} className="flex items-center gap-2 p-2 bg-slate-50 rounded-lg">
                <span className="text-sm font-medium flex-1">{med.name}</span>
                {med.frequency && <span className="text-xs text-muted-foreground">{med.frequency}</span>}
                <button
                  onClick={() => update({ medications: form.medications.filter((_, i) => i !== idx) })}
                  className="text-red-400 hover:text-red-600 text-xs"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Tên thuốc..."
              value={medInput}
              onChange={(e) => setMedInput(e.target.value)}
              className="flex-1"
            />
            <Input
              placeholder="Tần suất (VD: 2 lần/ngày)"
              value={medFreq}
              onChange={(e) => setMedFreq(e.target.value)}
              className="flex-1"
            />
            <Button onClick={addMedication} size="sm" variant="outline">+ Thêm</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Step 4: Lifestyle ────────────────────────────────────────────────────────

function StepLifestyle({
  form,
  update,
}: {
  form: WizardFormData;
  update: (p: Partial<WizardFormData>) => void;
}) {
  const mealFreqOptions: { value: MealFrequency; label: string }[] = [
    { value: "two_meals", label: "2 bữa/ngày" },
    { value: "three_meals", label: "3 bữa/ngày" },
    { value: "four_meals", label: "4 bữa/ngày" },
    { value: "five_plus", label: "5+ bữa nhỏ/ngày" },
    { value: "intermittent_fasting", label: "Nhịn ăn gián đoạn" },
  ];

  const cookingOptions: { value: CookingPreference; label: string }[] = [
    { value: "home_cooked", label: "Tự nấu ở nhà" },
    { value: "mixed", label: "Kết hợp" },
    { value: "eat_out", label: "Ăn ngoài thường xuyên" },
    { value: "meal_prep", label: "Chuẩn bị sẵn theo tuần" },
  ];

  const workScheduleOptions = [
    { value: "office_day", label: "Văn phòng giờ hành chính" },
    { value: "shift_work", label: "Ca kíp" },
    { value: "remote", label: "Làm việc từ xa" },
    { value: "freelance", label: "Tự do / Freelance" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Lối sống & Thói quen</CardTitle>
        <CardDescription>Thông tin về giấc ngủ, lịch trình và thói quen sinh hoạt.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">

        {/* Sleep Schedule */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Giờ thức dậy</Label>
            <Input
              type="time"
              value={form.wake_up_time}
              onChange={(e) => update({ wake_up_time: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>Giờ đi ngủ</Label>
            <Input
              type="time"
              value={form.sleep_time}
              onChange={(e) => update({ sleep_time: e.target.value })}
            />
          </div>
        </div>

        {/* Sleep Duration */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <Label>Thời lượng ngủ trung bình</Label>
            <span className="text-sm font-semibold text-emerald-600">
              ~{form.sleep_duration_hours}h
            </span>
          </div>
          <input
            type="range"
            min={4} max={12} step={0.5}
            value={form.sleep_duration_hours}
            onChange={(e) => update({ sleep_duration_hours: Number(e.target.value) })}
            className="w-full accent-emerald-500"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>4h</span><span>12h</span>
          </div>
        </div>

        {/* Sleep Quality */}
        <div className="space-y-2">
          <Label>Chất lượng giấc ngủ</Label>
          <div className="flex gap-2 flex-wrap">
            {(["poor", "fair", "good", "excellent"] as SleepQuality[]).map((q) => {
              const labels: Record<SleepQuality, string> = {
                poor: "Kém", fair: "Trung bình", good: "Tốt", excellent: "Rất tốt"
              };
              return (
                <button
                  key={q}
                  onClick={() => update({ sleep_quality: form.sleep_quality === q ? undefined : q })}
                  className={cn(
                    "px-4 py-2 rounded-full text-sm border transition-all font-medium",
                    form.sleep_quality === q
                      ? "bg-indigo-100 border-indigo-400 text-indigo-700"
                      : "border-slate-200 text-muted-foreground hover:border-indigo-200"
                  )}
                >
                  {labels[q]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Stress Level */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <Label>Mức độ căng thẳng (1-10)</Label>
            <span className={cn(
              "text-sm font-bold px-2 py-0.5 rounded-full",
              form.stress_level <= 3 ? "bg-green-100 text-green-700" :
              form.stress_level <= 6 ? "bg-amber-100 text-amber-700" :
              "bg-red-100 text-red-700"
            )}>
              {form.stress_level}/10
            </span>
          </div>
          <input
            type="range"
            min={1} max={10} step={1}
            value={form.stress_level}
            onChange={(e) => update({ stress_level: Number(e.target.value) })}
            className="w-full accent-emerald-500"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Bình thường</span><span>Rất căng thẳng</span>
          </div>
        </div>

        {/* Meal Frequency */}
        <div className="space-y-2">
          <Label>Tần suất bữa ăn</Label>
          <div className="flex flex-wrap gap-2">
            {mealFreqOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => update({ meal_frequency: form.meal_frequency === opt.value ? undefined : opt.value })}
                className={cn(
                  "px-3 py-2 rounded-lg text-sm border transition-all",
                  form.meal_frequency === opt.value
                    ? "bg-orange-50 border-orange-300 text-orange-700 font-medium"
                    : "border-slate-200 text-muted-foreground hover:border-orange-200"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Cooking Preference */}
        <div className="space-y-2">
          <Label>Thói quen nấu ăn</Label>
          <div className="flex flex-wrap gap-2">
            {cookingOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => update({ cooking_preference: opt.value })}
                className={cn(
                  "px-3 py-2 rounded-lg text-sm border transition-all",
                  form.cooking_preference === opt.value
                    ? "bg-emerald-50 border-emerald-300 text-emerald-700 font-medium"
                    : "border-slate-200 text-muted-foreground hover:border-emerald-200"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Work Schedule */}
        <div className="space-y-2">
          <Label>Lịch làm việc</Label>
          <div className="flex flex-wrap gap-2">
            {workScheduleOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => update({ work_schedule: form.work_schedule === opt.value ? "" : opt.value })}
                className={cn(
                  "px-3 py-2 rounded-lg text-sm border transition-all",
                  form.work_schedule === opt.value
                    ? "bg-blue-50 border-blue-300 text-blue-700 font-medium"
                    : "border-slate-200 text-muted-foreground hover:border-blue-200"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Step 5: Taste & Food Preferences ─────────────────────────────────────────

function StepTastePreferences({
  form,
  update,
}: {
  form: WizardFormData;
  update: (p: Partial<WizardFormData>) => void;
}) {
  const [dislikedInput, setDislikedInput] = useState("");
  const [favoriteInput, setFavoriteInput] = useState("");

  const tasteKeys = (["spicy", "sweet", "salty", "sour", "bitter"] as const);
  const tasteLabels: Record<string, string> = {
    spicy: "Cay 🌶️", sweet: "Ngọt 🍬", salty: "Mặn 🧂",
    sour: "Chua 🍋", bitter: "Đắng 🍵",
  };

  function updateTaste(key: keyof TastePreferencesSchema, value: number) {
    update({
      taste_preferences: { ...form.taste_preferences, [key]: value },
    });
  }

  function addDisliked() {
    if (!dislikedInput.trim()) return;
    if (!form.disliked_foods.includes(dislikedInput.trim())) {
      update({ disliked_foods: [...form.disliked_foods, dislikedInput.trim()] });
    }
    setDislikedInput("");
  }

  function addFavorite() {
    if (!favoriteInput.trim()) return;
    if (!form.favorite_foods.includes(favoriteInput.trim())) {
      update({ favorite_foods: [...form.favorite_foods, favoriteInput.trim()] });
    }
    setFavoriteInput("");
  }

  function toggleCuisine(cuisine: string) {
    if (form.cuisine_preferences.includes(cuisine)) {
      update({ cuisine_preferences: form.cuisine_preferences.filter((c) => c !== cuisine) });
    } else {
      update({ cuisine_preferences: [...form.cuisine_preferences, cuisine] });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Khẩu vị & Ẩm thực yêu thích</CardTitle>
        <CardDescription>
          Thông tin này giúp SmartMeal gợi ý món ăn phù hợp với khẩu vị của bạn.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">

        {/* Taste Sliders */}
        <div className="space-y-4">
          <Label>Mức độ khẩu vị (1-5)</Label>
          {tasteKeys.map((key) => (
            <div key={key} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span>{tasteLabels[key]}</span>
                <span className="font-semibold text-emerald-600">
                  {form.taste_preferences[key] ?? 3}/5
                </span>
              </div>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((v) => (
                  <button
                    key={v}
                    onClick={() => updateTaste(key, v)}
                    className={cn(
                      "flex-1 h-8 rounded-md border-2 transition-all text-xs font-bold",
                      (form.taste_preferences[key] ?? 3) >= v
                        ? "bg-emerald-500 border-emerald-500 text-white"
                        : "border-slate-200 text-muted-foreground hover:border-emerald-300"
                    )}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Cuisine Preferences */}
        <div className="space-y-2">
          <Label>Ẩm thực yêu thích (chọn nhiều)</Label>
          <div className="flex flex-wrap gap-2">
            {CUISINE_OPTIONS.map((cuisine) => {
              const selected = form.cuisine_preferences.includes(cuisine);
              return (
                <button
                  key={cuisine}
                  onClick={() => toggleCuisine(cuisine)}
                  className={cn(
                    "px-3 py-2 rounded-full text-xs font-medium border transition-all",
                    selected
                      ? "bg-emerald-100 border-emerald-400 text-emerald-700"
                      : "border-slate-200 text-muted-foreground hover:border-emerald-200"
                  )}
                >
                  {CUISINE_LABELS[cuisine] || cuisine}
                  {selected && " ✓"}
                </button>
              );
            })}
          </div>
        </div>

        {/* Eating Speed */}
        <div className="space-y-2">
          <Label>Tốc độ ăn</Label>
          <div className="flex gap-2">
            {(["slow", "normal", "fast"] as EatingSpeed[]).map((s) => {
              const labels: Record<EatingSpeed, string> = {
                slow: "Chậm 🐢", normal: "Bình thường 🚶", fast: "Nhanh ⚡"
              };
              return (
                <button
                  key={s}
                  onClick={() => update({ eating_speed: form.eating_speed === s ? undefined : s })}
                  className={cn(
                    "flex-1 py-2 rounded-lg text-sm border transition-all font-medium",
                    form.eating_speed === s
                      ? "bg-purple-50 border-purple-300 text-purple-700"
                      : "border-slate-200 text-muted-foreground hover:border-purple-200"
                  )}
                >
                  {labels[s]}
                </button>
              );
            })}
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={form.chew_difficulty}
              onChange={(e) => update({ chew_difficulty: e.target.checked })}
              className="accent-emerald-500"
            />
            Có khó khăn khi nhai (vấn đề răng miệng/hàm)
          </label>
        </div>

        {/* Disliked Foods */}
        <div className="space-y-2">
          <Label>Món không thích</Label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {form.disliked_foods.map((food) => (
              <span
                key={food}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-red-50 border border-red-200 rounded-full text-xs text-red-700"
              >
                {food}
                <button
                  onClick={() => update({ disliked_foods: form.disliked_foods.filter((f) => f !== food) })}
                  className="text-red-400 hover:text-red-600 ml-1"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="VD: gan, mướp đắng..."
              value={dislikedInput}
              onChange={(e) => setDislikedInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addDisliked()}
              className="flex-1"
            />
            <Button onClick={addDisliked} size="sm" variant="outline">+ Thêm</Button>
          </div>
        </div>

        {/* Favorite Foods */}
        <div className="space-y-2">
          <Label>Món yêu thích</Label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {form.favorite_foods.map((food) => (
              <span
                key={food}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 border border-emerald-200 rounded-full text-xs text-emerald-700"
              >
                {food}
                <button
                  onClick={() => update({ favorite_foods: form.favorite_foods.filter((f) => f !== food) })}
                  className="text-emerald-400 hover:text-emerald-600 ml-1"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="VD: ức gà, cơm gạo lứt..."
              value={favoriteInput}
              onChange={(e) => setFavoriteInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addFavorite()}
              className="flex-1"
            />
            <Button onClick={addFavorite} size="sm" variant="outline">+ Thêm</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
