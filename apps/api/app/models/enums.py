import enum


class GenderType(str, enum.Enum):
    nam = "nam"
    nu = "nu"
    khac = "khac"
    khong_muon_noi = "khong_muon_noi"

class ActivityLevelType(str, enum.Enum):
    it_van_dong = "it_van_dong"
    van_dong_nhe = "van_dong_nhe"
    van_dong_vua = "van_dong_vua"
    van_dong_nhieu = "van_dong_nhieu"
    van_dong_rat_nhieu = "van_dong_rat_nhieu"

class DietTypeEnum(str, enum.Enum):
    binh_thuong = "binh_thuong"
    an_chay = "an_chay"
    thuan_chay = "thuan_chay"
    keto = "keto"
    it_tinh_bot = "it_tinh_bot"
    nhieu_dam = "nhieu_dam"
    khac = "khac"

class NutritionGoalType(str, enum.Enum):
    giam_can = "giam_can"
    giu_can = "giu_can"
    tang_co = "tang_co"

class MealTypeEnum(str, enum.Enum):
    bua_sang = "bua_sang"
    bua_trua = "bua_trua"
    bua_toi = "bua_toi"
    an_vat = "an_vat"
    khac = "khac"

class FoodSourceType(str, enum.Enum):
    he_thong = "he_thong"
    usda = "usda"
    thu_cong = "thu_cong"
    ai_goi_y = "ai_goi_y"

class ItemSourceType(str, enum.Enum):
    ai_nhan_dien = "ai_nhan_dien"
    nguoi_dung_xac_nhan = "nguoi_dung_xac_nhan"
    nhap_thu_cong = "nhap_thu_cong"

class WorkoutDifficultyType(str, enum.Enum):
    nguoi_moi = "nguoi_moi"
    trung_binh = "trung_binh"
    nang_cao = "nang_cao"
