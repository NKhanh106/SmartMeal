"""Add pg_trgm GIN index for fast food search.

Adds pg_trgm extension and a GIN index on food_name to replace
LIKE/ilike prefix searches that cause full table scans.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260504_0001"
down_revision = "20260503_0002"  # latest existing migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable trigram similarity extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create GIN index using trigram similarity operator class
    # Covers all ilike patterns on food_name: prefix (x%), suffix (%x), and substring (%x%)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_food_name_trgm "
        "ON food_nutrition USING GIN (food_name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_food_name_trgm")
    # Do NOT drop pg_trgm extension — other tables or migrations may depend on it
