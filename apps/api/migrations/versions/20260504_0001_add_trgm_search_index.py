"""Add pg_trgm GIN indexes for fast food search.

Adds pg_trgm extension and GIN trigram indexes on food_name, food_name_vi,
food_name_en, and category columns to replace ILIKE substring searches that
cause full table scans on food_nutrition.

Covers:
- food_name: primary search column (ILIKE on normalized names, Stage 2 fallback)
- food_name_vi: Vietnamese name column (ILIKE in food_mapping_service)
- food_name_en: English name column (ILIKE in food_mapping_service)
- category: category filter (ILIKE in meal_extraction_service)

All indexes use CONCURRENTLY to avoid table locks during build.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260504_0001"
down_revision = "20260503_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable trigram similarity extension (idempotent — no-op if already exists)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # All CREATE INDEX CONCURRENTLY must run outside the default transaction block
    ctx = op.get_context()
    with ctx.autocommit_block():
        # Index on food_name: primary search column used in ILIKE '%...%' queries
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "idx_food_nutrition_name_trgm "
            "ON food_nutrition USING GIN (food_name gin_trgm_ops)"
        )

        # Index on food_name_vi: Vietnamese name ILIKE search in food_mapping_service
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "idx_food_nutrition_name_vi_trgm "
            "ON food_nutrition USING GIN (food_name_vi gin_trgm_ops)"
        )

        # Index on food_name_en: English name ILIKE search in food_mapping_service
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "idx_food_nutrition_name_en_trgm "
            "ON food_nutrition USING GIN (food_name_en gin_trgm_ops)"
        )

        # Index on category: ILIKE category filter in meal_extraction_service
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "idx_food_nutrition_category_trgm "
            "ON food_nutrition USING GIN (category gin_trgm_ops)"
        )


def downgrade() -> None:
    ctx = op.get_context()
    with ctx.autocommit_block():
        op.execute("DROP INDEX IF EXISTS idx_food_nutrition_name_trgm")
        op.execute("DROP INDEX IF EXISTS idx_food_nutrition_name_vi_trgm")
        op.execute("DROP INDEX IF EXISTS idx_food_nutrition_name_en_trgm")
        op.execute("DROP INDEX IF EXISTS idx_food_nutrition_category_trgm")
    # Do NOT drop pg_trgm extension — other tables or migrations may depend on it
