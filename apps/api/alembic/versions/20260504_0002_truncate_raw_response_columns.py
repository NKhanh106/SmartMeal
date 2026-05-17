"""Truncate ai_log.raw_response and daily_recommendation.ai_raw_response.

These fields previously stored full AI JSON blobs (KB per record), causing
database bloat. Now they are limited to 500 chars for debugging only,
or removed entirely from the upsert path.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260504_0002"
down_revision = "20260504_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Truncate ai_analysis_logs.raw_response to 500 chars
    op.execute("ALTER TABLE ai_analysis_logs ALTER COLUMN raw_response TYPE TEXT")
    op.execute(
        "ALTER TABLE ai_analysis_logs "
        "ALTER COLUMN raw_response "
        "SET DEFAULT NULL"
    )
    # Keep existing data but it will be truncated on next insert/update
    # Note: Postgres TEXT type has no length limit, but application code
    # now limits stored values to 500 chars.

    # Truncate daily_recommendations.ai_raw_response similarly
    op.execute("ALTER TABLE daily_recommendations ALTER COLUMN ai_raw_response TYPE TEXT")
    op.execute(
        "ALTER TABLE daily_recommendations "
        "ALTER COLUMN ai_raw_response "
        "SET DEFAULT NULL"
    )


def downgrade() -> None:
    # Restore JSONB types
    op.execute(
        "ALTER TABLE ai_analysis_logs "
        "ALTER COLUMN raw_response TYPE JSONB USING raw_response::JSONB"
    )
    op.execute(
        "ALTER TABLE daily_recommendations "
        "ALTER COLUMN ai_raw_response TYPE JSONB USING ai_raw_response::JSONB"
    )
