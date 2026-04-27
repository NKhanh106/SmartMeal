-- =========================================================
-- SmartMeal Database Schema - PostgreSQL 17+
-- 13 core tables:
-- 1. users
-- 2. user_profiles
-- 3. nutrition_goals
-- 4. food_nutrition
-- 5. meal_logs
-- 6. meal_items
-- 7. progress_logs
-- 8. workout_plans
-- 9. workout_items
-- 10. ai_analysis_logs
-- 11. daily_recommendations
-- 12. chat_sessions
-- 13. chat_messages
-- =========================================================

BEGIN;

-- =========================================================
-- EXTENSIONS
-- =========================================================

-- Case-insensitive email
CREATE EXTENSION IF NOT EXISTS citext;

-- Better text search for food names
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- =========================================================
-- ENUM TYPES
-- =========================================================

CREATE TYPE gender_type AS ENUM (
    'nam',
    'nu',
    'khac',
    'khong_muon_noi'
);

CREATE TYPE activity_level_type AS ENUM (
    'it_van_dong',
    'van_dong_nhe',
    'van_dong_vua',
    'van_dong_nhieu',
    'van_dong_rat_nhieu'
);

CREATE TYPE nutrition_goal_type AS ENUM (
    'giam_can',
    'giu_can',
    'tang_co'
);

CREATE TYPE meal_type_enum AS ENUM (
    'bua_sang',
    'bua_trua',
    'bua_toi',
    'an_vat',
    'khac'
);

CREATE TYPE food_source_type AS ENUM (
    'he_thong',
    'usda',
    'thu_cong',
    'ai_goi_y'
);

CREATE TYPE item_source_type AS ENUM (
    'ai_nhan_dien',
    'nguoi_dung_xac_nhan',
    'nhap_thu_cong'
);

CREATE TYPE workout_difficulty_type AS ENUM (
    'nguoi_moi',
    'trung_binh',
    'nang_cao'
);

CREATE TYPE diet_type_enum AS ENUM (
    'binh_thuong',
    'an_chay',
    'thuan_chay',
    'keto',
    'it_tinh_bot',
    'nhieu_dam',
    'khac'
);


-- =========================================================
-- UPDATED_AT TRIGGER FUNCTION
-- =========================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =========================================================
-- 1. USERS
-- Lưu tài khoản người dùng.
-- =========================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    email CITEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,

    full_name VARCHAR(255),
    avatar_url TEXT,

    role VARCHAR(20) NOT NULL DEFAULT 'user',

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,

    failed_login_attempts SMALLINT NOT NULL DEFAULT 0,
    login_allowed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,

    CONSTRAINT chk_users_email_not_blank
        CHECK (LENGTH(TRIM(email::TEXT)) > 0),

    CONSTRAINT chk_users_failed_login_attempts
        CHECK (failed_login_attempts >= 0),

    CONSTRAINT chk_users_role
        CHECK (role IN ('user', 'admin'))
);

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_users_active
ON users(id)
WHERE deleted_at IS NULL;

COMMENT ON TABLE users IS 'Tài khoản người dùng của hệ thống SmartMeal.';
COMMENT ON COLUMN users.password_hash IS 'Chỉ lưu mật khẩu đã hash, tuyệt đối không lưu plain text password.';
COMMENT ON COLUMN users.login_allowed_at IS 'Thời điểm sớm nhất user được phép login. Khi nhập sai password nhiều lần, set = NOW() + 5 phút để rate-limit.';
COMMENT ON COLUMN users.failed_login_attempts IS 'Số lần nhập sai password liên tiếp. Reset về 0 khi login thành công.';
COMMENT ON COLUMN users.deleted_at IS 'Soft-delete: NULL = active, có giá trị = đã xóa. Dùng thay cho hard delete để giữ audit trail.';


-- =========================================================
-- 2. USER_PROFILES
-- Hồ sơ thể chất và thông tin cá nhân hóa dinh dưỡng của người dùng.
-- Dùng để tính BMI, BMR, TDEE, macro và cá nhân hóa khuyến nghị.
-- =========================================================

CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL UNIQUE
        REFERENCES users(id)
        ON DELETE CASCADE,

    gender gender_type NOT NULL,
    date_of_birth DATE NOT NULL,

    height_cm NUMERIC(6,2) NOT NULL,
    current_weight_kg NUMERIC(6,2) NOT NULL,

    current_body_fat_percent NUMERIC(5,2),
    current_waist_cm NUMERIC(5,2),
    current_neck_cm NUMERIC(5,2),
    current_hip_cm NUMERIC(5,2),
    current_chest_cm NUMERIC(5,2),

    activity_level activity_level_type NOT NULL DEFAULT 'it_van_dong',

    diet_type diet_type_enum NOT NULL DEFAULT 'binh_thuong',
    allergies TEXT,
    disliked_foods TEXT,
    preferred_foods TEXT,

    health_note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_profile_birth_date
        CHECK (date_of_birth <= CURRENT_DATE),

    CONSTRAINT chk_profile_height
        CHECK (height_cm BETWEEN 50 AND 250),

    CONSTRAINT chk_profile_weight
        CHECK (current_weight_kg BETWEEN 20 AND 300),

    CONSTRAINT chk_profile_body_fat
        CHECK (
            current_body_fat_percent IS NULL
            OR current_body_fat_percent BETWEEN 1 AND 80
        ),

    CONSTRAINT chk_profile_waist
        CHECK (
            current_waist_cm IS NULL
            OR current_waist_cm BETWEEN 30 AND 250
        ),

    CONSTRAINT chk_profile_neck
        CHECK (
            current_neck_cm IS NULL
            OR current_neck_cm BETWEEN 20 AND 80
        ),

    CONSTRAINT chk_profile_hip
        CHECK (
            current_hip_cm IS NULL
            OR current_hip_cm BETWEEN 30 AND 250
        ),

    CONSTRAINT chk_profile_chest
        CHECK (
            current_chest_cm IS NULL
            OR current_chest_cm BETWEEN 30 AND 250
        )
);

CREATE INDEX idx_user_profiles_activity_level
ON user_profiles(activity_level);

CREATE INDEX idx_user_profiles_diet_type
ON user_profiles(diet_type);

CREATE TRIGGER trg_user_profiles_updated_at
BEFORE UPDATE ON user_profiles
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE user_profiles IS 'Hồ sơ thể chất và thông tin cá nhân hóa dinh dưỡng của người dùng trong SmartMeal.';
COMMENT ON COLUMN user_profiles.user_id IS 'Mỗi user chỉ có một profile hiện tại.';
COMMENT ON COLUMN user_profiles.date_of_birth IS 'Lưu ngày sinh thay vì tuổi vì tuổi thay đổi theo thời gian.';
COMMENT ON COLUMN user_profiles.height_cm IS 'Chiều cao hiện tại của người dùng, dùng để tính BMI và BMR.';
COMMENT ON COLUMN user_profiles.current_weight_kg IS 'Cân nặng hiện tại, dùng để tính BMI, BMR, TDEE và mục tiêu dinh dưỡng.';
COMMENT ON COLUMN user_profiles.activity_level IS 'Mức độ vận động, dùng để quy đổi BMR sang TDEE.';
COMMENT ON COLUMN user_profiles.current_waist_cm IS 'Vòng eo, có thể dùng để ước lượng body fat và theo dõi tiến độ vóc dáng.';
COMMENT ON COLUMN user_profiles.current_neck_cm IS 'Vòng cổ, cần thiết nếu dùng công thức Navy Body Fat để ước lượng tỷ lệ mỡ cơ thể.';
COMMENT ON COLUMN user_profiles.current_hip_cm IS 'Vòng hông, đặc biệt hữu ích khi ước lượng body fat cho nữ hoặc tính tỷ lệ eo/hông.';
COMMENT ON COLUMN user_profiles.diet_type IS 'Kiểu chế độ ăn: bình thường, chay, thuần chay, keto, ít tinh bột, nhiều đạm...';
COMMENT ON COLUMN user_profiles.allergies IS 'Danh sách dị ứng thực phẩm, lưu dạng text phân tách bằng dấu phẩy ở MVP.';
COMMENT ON COLUMN user_profiles.disliked_foods IS 'Các món người dùng không thích, phục vụ cá nhân hóa gợi ý thực đơn.';
COMMENT ON COLUMN user_profiles.preferred_foods IS 'Các món người dùng ưa thích, phục vụ cá nhân hóa gợi ý thực đơn.';


-- =========================================================
-- 3. NUTRITION_GOALS
-- Lưu mục tiêu dinh dưỡng của người dùng.
-- Một user có thể có nhiều goal theo thời gian,
-- nhưng chỉ nên có 1 goal active tại một thời điểm.
-- =========================================================

CREATE TABLE nutrition_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    goal_type nutrition_goal_type NOT NULL,

    target_weight_kg NUMERIC(6,2),

    bmr_kcal NUMERIC(8,2),
    tdee_kcal NUMERIC(8,2),
    bmi NUMERIC(5,2),

    daily_calorie_target NUMERIC(8,2),
    protein_target_g NUMERIC(8,2),
    carb_target_g NUMERIC(8,2),
    fat_target_g NUMERIC(8,2),

    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_goal_target_weight
        CHECK (target_weight_kg IS NULL OR target_weight_kg BETWEEN 20 AND 300),

    CONSTRAINT chk_goal_bmr
        CHECK (bmr_kcal IS NULL OR bmr_kcal BETWEEN 500 AND 5000),

    CONSTRAINT chk_goal_tdee
        CHECK (tdee_kcal IS NULL OR tdee_kcal BETWEEN 500 AND 8000),

    CONSTRAINT chk_goal_bmi
        CHECK (bmi IS NULL OR bmi BETWEEN 5 AND 100),

    CONSTRAINT chk_goal_calorie_target
        CHECK (daily_calorie_target IS NULL OR daily_calorie_target BETWEEN 500 AND 8000),

    CONSTRAINT chk_goal_macro_targets
        CHECK (
            (protein_target_g IS NULL OR protein_target_g >= 0)
            AND (carb_target_g IS NULL OR carb_target_g >= 0)
            AND (fat_target_g IS NULL OR fat_target_g >= 0)
        ),

    CONSTRAINT chk_goal_date_range
        CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX idx_nutrition_goals_user_id
ON nutrition_goals(user_id);

CREATE UNIQUE INDEX uq_nutrition_goals_id_user_id
ON nutrition_goals(id, user_id);

CREATE UNIQUE INDEX uq_nutrition_goals_one_active_per_user
ON nutrition_goals(user_id)
WHERE is_active = TRUE;

CREATE TRIGGER trg_nutrition_goals_updated_at
BEFORE UPDATE ON nutrition_goals
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE nutrition_goals IS 'Mục tiêu dinh dưỡng của user: giảm cân, giữ cân, tăng cơ; lưu snapshot BMR/TDEE/macro tại thời điểm tạo goal.';


-- =========================================================
-- 4. FOOD_NUTRITION
-- Cơ sở dữ liệu dinh dưỡng chuẩn.
-- Dùng đơn vị per 100g để dễ tính toán.
-- =========================================================

CREATE TABLE food_nutrition (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    food_name VARCHAR(255) NOT NULL,
    food_name_vi VARCHAR(255),
    food_name_en VARCHAR(255),

    category VARCHAR(100),

    serving_size_g NUMERIC(8,2) NOT NULL DEFAULT 100,

    calories_per_100g NUMERIC(8,2) NOT NULL DEFAULT 0,
    protein_per_100g NUMERIC(8,2) NOT NULL DEFAULT 0,
    carb_per_100g NUMERIC(8,2) NOT NULL DEFAULT 0,
    fat_per_100g NUMERIC(8,2) NOT NULL DEFAULT 0,

    fiber_per_100g NUMERIC(8,2),
    sugar_per_100g NUMERIC(8,2),
    sodium_mg_per_100g NUMERIC(8,2),

    source food_source_type NOT NULL DEFAULT 'he_thong',
    external_id VARCHAR(255),

    is_verified BOOLEAN NOT NULL DEFAULT FALSE,

    created_by_user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_food_name_not_blank
        CHECK (LENGTH(TRIM(food_name)) > 0),

    CONSTRAINT chk_food_serving_size
        CHECK (serving_size_g > 0),

    CONSTRAINT chk_food_macros_non_negative
        CHECK (
            calories_per_100g >= 0
            AND protein_per_100g >= 0
            AND carb_per_100g >= 0
            AND fat_per_100g >= 0
        ),

    CONSTRAINT chk_food_extra_nutrients_non_negative
        CHECK (
            (fiber_per_100g IS NULL OR fiber_per_100g >= 0)
            AND (sugar_per_100g IS NULL OR sugar_per_100g >= 0)
            AND (sodium_mg_per_100g IS NULL OR sodium_mg_per_100g >= 0)
        )
);

CREATE INDEX idx_food_nutrition_food_name
ON food_nutrition(food_name);

CREATE INDEX idx_food_nutrition_food_name_trgm
ON food_nutrition
USING GIN (food_name gin_trgm_ops);

CREATE INDEX idx_food_nutrition_category
ON food_nutrition(category);

CREATE UNIQUE INDEX uq_food_name_source
ON food_nutrition(food_name, source);

CREATE TRIGGER trg_food_nutrition_updated_at
BEFORE UPDATE ON food_nutrition
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE food_nutrition IS 'Bảng dữ liệu dinh dưỡng chuẩn của thực phẩm/món ăn, tính theo đơn vị 100g.';
COMMENT ON COLUMN food_nutrition.calories_per_100g IS 'Năng lượng kcal trên 100g thực phẩm.';


-- =========================================================
-- 5. MEAL_LOGS
-- Mỗi bản ghi là một bữa ăn/lần ghi nhận bữa ăn.
-- Tổng calories/macro được lưu snapshot để dashboard truy vấn nhanh.
-- =========================================================

CREATE TABLE meal_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    nutrition_goal_id UUID,

    CONSTRAINT fk_meal_logs_nutrition_goal
        FOREIGN KEY (nutrition_goal_id, user_id)
        REFERENCES nutrition_goals(id, user_id)
        ON DELETE SET NULL (nutrition_goal_id),

    meal_type meal_type_enum NOT NULL DEFAULT 'khac',

    meal_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    image_url TEXT,
    image_storage_path TEXT,

    ai_model VARCHAR(100),
    ai_confidence NUMERIC(5,4),

    total_calories NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_protein_g NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_carb_g NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_fat_g NUMERIC(10,2) NOT NULL DEFAULT 0,

    note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_meal_ai_confidence
        CHECK (ai_confidence IS NULL OR ai_confidence BETWEEN 0 AND 1),

    CONSTRAINT chk_meal_totals_non_negative
        CHECK (
            total_calories >= 0
            AND total_protein_g >= 0
            AND total_carb_g >= 0
            AND total_fat_g >= 0
        )
);

CREATE INDEX idx_meal_logs_user_id
ON meal_logs(user_id);

CREATE INDEX idx_meal_logs_user_time
ON meal_logs(user_id, meal_time DESC);

CREATE INDEX idx_meal_logs_goal_id
ON meal_logs(nutrition_goal_id);

CREATE TRIGGER trg_meal_logs_updated_at
BEFORE UPDATE ON meal_logs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE meal_logs IS 'Lịch sử bữa ăn của người dùng, có thể gắn ảnh và kết quả phân tích AI.';
COMMENT ON COLUMN meal_logs.total_calories IS 'Tổng calories snapshot, do backend tính từ meal_items để dashboard truy vấn nhanh.';


-- =========================================================
-- 6. MEAL_ITEMS
-- Mỗi bữa ăn có thể gồm nhiều món/thực phẩm.
-- =========================================================

CREATE TABLE meal_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    meal_log_id UUID NOT NULL
        REFERENCES meal_logs(id)
        ON DELETE CASCADE,

    food_nutrition_id UUID
        REFERENCES food_nutrition(id)
        ON DELETE SET NULL,

    detected_food_name VARCHAR(255) NOT NULL,
    display_food_name VARCHAR(255),

    estimated_weight_g NUMERIC(10,2),

    calories NUMERIC(10,2) NOT NULL DEFAULT 0,
    protein_g NUMERIC(10,2) NOT NULL DEFAULT 0,
    carb_g NUMERIC(10,2) NOT NULL DEFAULT 0,
    fat_g NUMERIC(10,2) NOT NULL DEFAULT 0,

    confidence NUMERIC(5,4),

    source item_source_type NOT NULL DEFAULT 'ai_nhan_dien',

    ai_raw_result JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_meal_item_name_not_blank
        CHECK (LENGTH(TRIM(detected_food_name)) > 0),

    CONSTRAINT chk_meal_item_weight
        CHECK (estimated_weight_g IS NULL OR estimated_weight_g > 0),

    CONSTRAINT chk_meal_item_nutrients_non_negative
        CHECK (
            calories >= 0
            AND protein_g >= 0
            AND carb_g >= 0
            AND fat_g >= 0
        ),

    CONSTRAINT chk_meal_item_confidence
        CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)
);

CREATE INDEX idx_meal_items_meal_log_id
ON meal_items(meal_log_id);

CREATE INDEX idx_meal_items_food_nutrition_id
ON meal_items(food_nutrition_id);

CREATE INDEX idx_meal_items_detected_food_name_trgm
ON meal_items
USING GIN (detected_food_name gin_trgm_ops);

CREATE TRIGGER trg_meal_items_updated_at
BEFORE UPDATE ON meal_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE meal_items IS 'Chi tiết từng món ăn/thực phẩm trong một meal_log.';
COMMENT ON COLUMN meal_items.ai_raw_result IS 'Lưu JSON kết quả thô từ AI để debug/review, không nên hiển thị trực tiếp cho user.';


-- =========================================================
-- 7. PROGRESS_LOGS
-- Lưu tiến độ cơ thể theo ngày.
-- =========================================================

CREATE TABLE progress_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    log_date DATE NOT NULL DEFAULT CURRENT_DATE,

    weight_kg NUMERIC(6,2),
    body_fat_percent NUMERIC(5,2),
    waist_cm NUMERIC(5,2),
    neck_cm NUMERIC(5,2),
    chest_cm NUMERIC(5,2),
    hip_cm NUMERIC(5,2),

    progress_photo_url TEXT,

    note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_progress_user_date
        UNIQUE (user_id, log_date),

    CONSTRAINT chk_progress_weight
        CHECK (weight_kg IS NULL OR weight_kg BETWEEN 20 AND 300),

    CONSTRAINT chk_progress_body_fat
        CHECK (body_fat_percent IS NULL OR body_fat_percent BETWEEN 1 AND 80),

    CONSTRAINT chk_progress_measurements
        CHECK (
            (waist_cm IS NULL OR waist_cm BETWEEN 30 AND 250)
            AND (neck_cm IS NULL OR neck_cm BETWEEN 20 AND 80)
            AND (chest_cm IS NULL OR chest_cm BETWEEN 30 AND 250)
            AND (hip_cm IS NULL OR hip_cm BETWEEN 30 AND 250)
        )
);

CREATE INDEX idx_progress_logs_user_date
ON progress_logs(user_id, log_date DESC);

CREATE TRIGGER trg_progress_logs_updated_at
BEFORE UPDATE ON progress_logs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE progress_logs IS 'Dữ liệu tiến độ của user theo ngày: cân nặng, body fat, số đo cơ thể, ảnh tiến độ.';


-- =========================================================
-- 8. WORKOUT_PLANS
-- Kế hoạch luyện tập của người dùng.
-- Một user có thể có nhiều plan theo thời gian,
-- nhưng chỉ nên có 1 plan active.
-- =========================================================

CREATE TABLE workout_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    plan_name VARCHAR(255) NOT NULL,

    goal_type nutrition_goal_type,

    difficulty workout_difficulty_type NOT NULL DEFAULT 'nguoi_moi',

    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_workout_plan_name_not_blank
        CHECK (LENGTH(TRIM(plan_name)) > 0),

    CONSTRAINT chk_workout_plan_date_range
        CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX idx_workout_plans_user_id
ON workout_plans(user_id);

CREATE UNIQUE INDEX uq_workout_plans_one_active_per_user
ON workout_plans(user_id)
WHERE is_active = TRUE;

CREATE TRIGGER trg_workout_plans_updated_at
BEFORE UPDATE ON workout_plans
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE workout_plans IS 'Kế hoạch luyện tập của người dùng theo mục tiêu và độ khó.';


-- =========================================================
-- 9. WORKOUT_ITEMS
-- Chi tiết từng bài tập trong workout plan.
-- MVP đang gộp cả bài tập dự kiến và trạng thái hoàn thành.
-- Khi mở rộng production có thể tách thêm workout_logs.
-- =========================================================

CREATE TABLE workout_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workout_plan_id UUID NOT NULL
        REFERENCES workout_plans(id)
        ON DELETE CASCADE,

    workout_date DATE,

    day_of_week SMALLINT,

    muscle_group VARCHAR(100),
    exercise_name VARCHAR(255) NOT NULL,

    weight_kg NUMERIC(6,2),

    sets INT,
    reps INT,
    duration_minutes INT,
    rest_seconds INT,

    order_index INT NOT NULL DEFAULT 0,

    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMPTZ,

    note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_workout_day_of_week
        CHECK (day_of_week IS NULL OR day_of_week BETWEEN 1 AND 7),

    CONSTRAINT chk_workout_exercise_name_not_blank
        CHECK (LENGTH(TRIM(exercise_name)) > 0),

    CONSTRAINT chk_workout_sets_reps
        CHECK (
            (sets IS NULL OR sets > 0)
            AND (reps IS NULL OR reps > 0)
        ),

    CONSTRAINT chk_workout_duration_rest
        CHECK (
            (duration_minutes IS NULL OR duration_minutes > 0)
            AND (rest_seconds IS NULL OR rest_seconds >= 0)
        ),

    CONSTRAINT chk_workout_weight
        CHECK (weight_kg IS NULL OR weight_kg > 0),

    CONSTRAINT chk_workout_completed_at
        CHECK (
            (is_completed = FALSE AND completed_at IS NULL)
            OR
            (is_completed = TRUE AND completed_at IS NOT NULL)
        )
);

CREATE INDEX idx_workout_items_plan_id
ON workout_items(workout_plan_id);

CREATE INDEX idx_workout_items_plan_date
ON workout_items(workout_plan_id, workout_date);

CREATE INDEX idx_workout_items_muscle_group
ON workout_items(muscle_group);

CREATE TRIGGER trg_workout_items_updated_at
BEFORE UPDATE ON workout_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE workout_items IS 'Danh sách bài tập trong kế hoạch luyện tập. MVP có thể lưu luôn trạng thái hoàn thành tại đây.';


-- =========================================================
-- 10. AI_ANALYSIS_LOGS
-- Lưu log tất cả lần gọi AI:
-- meal image analysis, daily recommendation, chatbot.
-- Dùng để debug, audit, đo latency và theo dõi provider/model.
-- =========================================================

CREATE TABLE ai_analysis_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    task_type VARCHAR(100) NOT NULL,
    -- meal_image_analysis | daily_recommendation | chatbot

    provider_name VARCHAR(50),
    -- gemini | groq | other

    model_name VARCHAR(100),
    prompt_version VARCHAR(50),

    input_summary TEXT,
    raw_response JSONB,

    status VARCHAR(50) NOT NULL DEFAULT 'success',
    -- success | failed

    error_message TEXT,

    latency_ms INT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_ai_logs_task_type_not_blank
        CHECK (LENGTH(TRIM(task_type)) > 0),

    CONSTRAINT chk_ai_logs_status
        CHECK (status IN ('success', 'failed')),

    CONSTRAINT chk_ai_logs_provider_name
        CHECK (
            provider_name IS NULL
            OR LENGTH(TRIM(provider_name)) > 0
        ),

    CONSTRAINT chk_ai_logs_latency
        CHECK (latency_ms IS NULL OR latency_ms >= 0)
);

CREATE INDEX idx_ai_logs_user_id
ON ai_analysis_logs(user_id);

CREATE INDEX idx_ai_logs_task_type
ON ai_analysis_logs(task_type);

CREATE INDEX idx_ai_logs_provider_name
ON ai_analysis_logs(provider_name);

CREATE INDEX idx_ai_logs_status
ON ai_analysis_logs(status);

CREATE INDEX idx_ai_logs_created_at
ON ai_analysis_logs(created_at DESC);

COMMENT ON TABLE ai_analysis_logs IS 'Lưu log các lần gọi AI trong hệ thống SmartMeal, bao gồm phân tích ảnh bữa ăn, sinh gợi ý hằng ngày và chatbot.';
COMMENT ON COLUMN ai_analysis_logs.task_type IS 'Loại tác vụ AI: meal_image_analysis, daily_recommendation hoặc chatbot.';
COMMENT ON COLUMN ai_analysis_logs.provider_name IS 'Tên nhà cung cấp AI được sử dụng, ví dụ: gemini hoặc groq.';
COMMENT ON COLUMN ai_analysis_logs.model_name IS 'Tên model AI được sử dụng trong lần gọi.';
COMMENT ON COLUMN ai_analysis_logs.prompt_version IS 'Phiên bản prompt, dùng để audit và so sánh hiệu quả prompt.';
COMMENT ON COLUMN ai_analysis_logs.raw_response IS 'Lưu response thô hoặc response đã parse từ AI, phục vụ debug và audit.';
COMMENT ON COLUMN ai_analysis_logs.latency_ms IS 'Thời gian xử lý của AI tính bằng millisecond.';


-- =========================================================
-- 11. DAILY_RECOMMENDATIONS
-- Lưu gợi ý hằng ngày do AI sinh ra.
-- Dữ liệu này dùng cho màn Daily Planner và làm context cho chatbot.
-- =========================================================

CREATE TABLE daily_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    recommendation_date DATE NOT NULL,

    calories_target NUMERIC(8,2),
    protein_target_g NUMERIC(8,2),
    carb_target_g NUMERIC(8,2),
    fat_target_g NUMERIC(8,2),

    meal_suggestion TEXT,
    workout_suggestion TEXT,
    lifestyle_suggestion TEXT,

    ai_summary TEXT,
    ai_raw_response JSONB,

    ai_analysis_log_id UUID
        REFERENCES ai_analysis_logs(id)
        ON DELETE SET NULL,

    status VARCHAR(50) NOT NULL DEFAULT 'generated',
    -- generated | accepted | rejected | expired

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_daily_recommendation_user_date
        UNIQUE(user_id, recommendation_date),

    CONSTRAINT chk_daily_recommendation_status
        CHECK (status IN ('generated', 'accepted', 'rejected', 'expired')),

    CONSTRAINT chk_daily_recommendation_targets
        CHECK (
            (calories_target IS NULL OR calories_target >= 0)
            AND (protein_target_g IS NULL OR protein_target_g >= 0)
            AND (carb_target_g IS NULL OR carb_target_g >= 0)
            AND (fat_target_g IS NULL OR fat_target_g >= 0)
        )
);

CREATE INDEX idx_daily_recommendations_user_date
ON daily_recommendations(user_id, recommendation_date DESC);

CREATE INDEX idx_daily_recommendations_status
ON daily_recommendations(status);

CREATE INDEX idx_daily_recommendations_ai_log_id
ON daily_recommendations(ai_analysis_log_id);

CREATE TRIGGER trg_daily_recommendations_updated_at
BEFORE UPDATE ON daily_recommendations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE daily_recommendations IS 'Lưu gợi ý ăn uống, luyện tập và sinh hoạt hằng ngày do AI sinh ra dựa trên hồ sơ, mục tiêu và lịch sử sinh hoạt của user.';
COMMENT ON COLUMN daily_recommendations.recommendation_date IS 'Ngày mà gợi ý này áp dụng. Thường là ngày tiếp theo so với thời điểm sinh gợi ý.';
COMMENT ON COLUMN daily_recommendations.ai_summary IS 'Tóm tắt lý do AI đưa ra gợi ý.';
COMMENT ON COLUMN daily_recommendations.ai_raw_response IS 'Lưu JSON response từ AI để debug hoặc kiểm tra lại.';
COMMENT ON COLUMN daily_recommendations.ai_analysis_log_id IS 'Liên kết tới bản ghi ai_analysis_logs tương ứng với lần sinh gợi ý này.';


-- =========================================================
-- 12. CHAT_SESSIONS
-- Quản lý các cuộc trò chuyện chatbot của user.
-- Một user có thể có nhiều chat session.
-- =========================================================

CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    title VARCHAR(255),

    status VARCHAR(50) NOT NULL DEFAULT 'active',
    -- active | archived | deleted

    last_message_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_chat_sessions_status
        CHECK (status IN ('active', 'archived', 'deleted')),

    CONSTRAINT chk_chat_sessions_title
        CHECK (
            title IS NULL
            OR LENGTH(TRIM(title)) > 0
        )
);

CREATE INDEX idx_chat_sessions_user_id
ON chat_sessions(user_id);

CREATE INDEX idx_chat_sessions_status
ON chat_sessions(status);

CREATE INDEX idx_chat_sessions_last_message_at
ON chat_sessions(last_message_at DESC);

CREATE INDEX idx_chat_sessions_created_at
ON chat_sessions(created_at DESC);

CREATE TRIGGER trg_chat_sessions_updated_at
BEFORE UPDATE ON chat_sessions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE chat_sessions IS 'Lưu các phiên trò chuyện chatbot của người dùng. Mỗi session là một cuộc trò chuyện riêng.';
COMMENT ON COLUMN chat_sessions.title IS 'Tiêu đề cuộc trò chuyện, có thể sinh từ tin nhắn đầu tiên của user.';
COMMENT ON COLUMN chat_sessions.status IS 'Trạng thái session: active, archived hoặc deleted.';
COMMENT ON COLUMN chat_sessions.last_message_at IS 'Thời điểm tin nhắn gần nhất, dùng để sắp xếp danh sách cuộc trò chuyện.';


-- =========================================================
-- 13. CHAT_MESSAGES
-- Lưu từng tin nhắn trong một chat session.
-- Bao gồm tin nhắn của user, assistant và system nếu cần.
-- =========================================================

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    session_id UUID NOT NULL
        REFERENCES chat_sessions(id)
        ON DELETE CASCADE,

    ai_analysis_log_id UUID
        REFERENCES ai_analysis_logs(id)
        ON DELETE SET NULL,

    role VARCHAR(50) NOT NULL,
    -- user | assistant | system

    content TEXT NOT NULL,

    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_chat_messages_role
        CHECK (role IN ('user', 'assistant', 'system')),

    CONSTRAINT chk_chat_messages_content_not_blank
        CHECK (LENGTH(TRIM(content)) > 0)
);

CREATE INDEX idx_chat_messages_session_id
ON chat_messages(session_id);

CREATE INDEX idx_chat_messages_session_created_at
ON chat_messages(session_id, created_at ASC);

CREATE INDEX idx_chat_messages_role
ON chat_messages(role);

CREATE INDEX idx_chat_messages_ai_log_id
ON chat_messages(ai_analysis_log_id);

CREATE INDEX idx_chat_messages_created_at
ON chat_messages(created_at DESC);

COMMENT ON TABLE chat_messages IS 'Lưu từng tin nhắn trong chatbot, bao gồm tin nhắn của người dùng, phản hồi của assistant và system message nếu có.';
COMMENT ON COLUMN chat_messages.ai_analysis_log_id IS 'Liên kết tin nhắn assistant với log AI tương ứng để truy vết provider/model/prompt/latency.';
COMMENT ON COLUMN chat_messages.role IS 'Vai trò của tin nhắn: user, assistant hoặc system.';
COMMENT ON COLUMN chat_messages.metadata IS 'Lưu metadata bổ sung như provider, model, prompt_version, context_size hoặc thông tin debug.';


-- =========================================================
-- OPTIONAL SEED DATA
-- Dữ liệu mẫu ban đầu cho bảng food_nutrition.
-- Có thể xóa nếu chưa cần.
-- =========================================================

INSERT INTO food_nutrition (
    food_name,
    food_name_vi,
    food_name_en,
    category,
    serving_size_g,
    calories_per_100g,
    protein_per_100g,
    carb_per_100g,
    fat_per_100g,
    source,
    is_verified
)
VALUES
    ('Cơm trắng', 'Cơm trắng', 'White rice', 'grain', 100, 130, 2.7, 28.2, 0.3, 'he_thong', TRUE),
    ('Ức gà luộc', 'Ức gà luộc', 'Boiled chicken breast', 'meat', 100, 165, 31.0, 0.0, 3.6, 'he_thong', TRUE),
    ('Trứng gà', 'Trứng gà', 'Chicken egg', 'egg', 100, 155, 13.0, 1.1, 11.0, 'he_thong', TRUE),
    ('Chuối', 'Chuối', 'Banana', 'fruit', 100, 89, 1.1, 22.8, 0.3, 'he_thong', TRUE),
    ('Khoai lang', 'Khoai lang', 'Sweet potato', 'tuber', 100, 86, 1.6, 20.1, 0.1, 'he_thong', TRUE);

COMMIT;
