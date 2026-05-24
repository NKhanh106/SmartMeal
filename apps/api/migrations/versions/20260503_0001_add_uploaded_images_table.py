"""add uploaded_images table for image management

Revision ID: 20260503_0001
Revises: 20260429_0002
Create Date: 2026-05-03

Adds:
- table: uploaded_images
  Stores metadata for all uploaded images (avatars, meal photos, progress photos).
  File binary is stored on disk; DB stores path, dimensions, checksum, TTL info.
- index: uploaded_images.user_id
- index: uploaded_images.image_type
- index: uploaded_images.created_at
- index: uploaded_images.expires_at
- index: uploaded_images.deleted_at
- composite index: (user_id, image_type)
- composite index: (expires_at, deleted_at)  -- for fast cleanup
- composite index: (linked_entity_type, linked_entity_id)  -- for linking to meal_logs etc.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260503_0001"
down_revision = "20260429_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uploaded_images",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "image_type",
            sa.String(50),
            nullable=False,
            server_default="meal",
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("linked_entity_type", sa.String(50), nullable=True),
        sa.Column("linked_entity_id", sa.UUID(), nullable=True),
    )

    # ── Indexes ─────────────────────────────────────────────────────────────────
    op.create_index("idx_uploaded_images_user_id", "uploaded_images", ["user_id"])
    op.create_index(
        "idx_uploaded_images_user_type", "uploaded_images", ["user_id", "image_type"]
    )
    op.create_index(
        "idx_uploaded_images_expires_deleted",
        "uploaded_images",
        ["expires_at", "deleted_at"],
    )
    op.create_index(
        "idx_uploaded_images_linked",
        "uploaded_images",
        ["linked_entity_type", "linked_entity_id"],
    )

    # ── Auto-update updated_at trigger ─────────────────────────────────────────
    op.execute(
        """
        CREATE TRIGGER trg_uploaded_images_updated_at
        BEFORE UPDATE ON uploaded_images
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_uploaded_images_updated_at ON uploaded_images")
    op.drop_index("idx_uploaded_images_linked", table_name="uploaded_images")
    op.drop_index("idx_uploaded_images_expires_deleted", table_name="uploaded_images")
    op.drop_index("idx_uploaded_images_user_type", table_name="uploaded_images")
    op.drop_index("idx_uploaded_images_user_id", table_name="uploaded_images")
    op.drop_table("uploaded_images")
