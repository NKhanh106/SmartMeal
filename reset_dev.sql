-- =========================================================
-- SmartMeal - Reset Dev Database
-- CHỈ DÙNG TRONG GIAI ĐOẠN PHÁT TRIỂN.
-- File này sẽ XÓA TOÀN BỘ schema và dữ liệu.
-- TUYỆT ĐỐI KHÔNG chạy trên môi trường có dữ liệu thật.
-- =========================================================

BEGIN;

-- Drop tables (thứ tự ngược theo dependency)
DROP TABLE IF EXISTS workout_items CASCADE;
DROP TABLE IF EXISTS workout_plans CASCADE;
DROP TABLE IF EXISTS progress_logs CASCADE;
DROP TABLE IF EXISTS meal_items CASCADE;
DROP TABLE IF EXISTS meal_logs CASCADE;
DROP TABLE IF EXISTS food_nutrition CASCADE;
DROP TABLE IF EXISTS nutrition_goals CASCADE;
DROP TABLE IF EXISTS user_profiles CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Drop enum types
DROP TYPE IF EXISTS gender_type CASCADE;
DROP TYPE IF EXISTS activity_level_type CASCADE;
DROP TYPE IF EXISTS nutrition_goal_type CASCADE;
DROP TYPE IF EXISTS meal_type_enum CASCADE;
DROP TYPE IF EXISTS food_source_type CASCADE;
DROP TYPE IF EXISTS item_source_type CASCADE;
DROP TYPE IF EXISTS workout_difficulty_type CASCADE;
DROP TYPE IF EXISTS diet_type_enum CASCADE;

-- Drop trigger function
DROP FUNCTION IF EXISTS set_updated_at() CASCADE;

COMMIT;
