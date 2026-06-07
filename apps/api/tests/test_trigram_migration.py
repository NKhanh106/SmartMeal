"""Tests for trigram index migration file content."""

import re


def _read_upgrade_source() -> str:
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "..", "migrations", "versions", "20260504_0001_add_trgm_search_index.py")
    with open(path, encoding="utf-8") as f:
        source = f.read()
    start = source.index("def upgrade()")
    end = source.index("def downgrade()")
    return source[start:end]


def _read_downgrade_source() -> str:
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "..", "migrations", "versions", "20260504_0001_add_trgm_search_index.py")
    with open(path, encoding="utf-8") as f:
        source = f.read()
    start = source.index("def downgrade()")
    return source[start:]


class TestTrigramMigrationStructure:
    def test_revision_identifiers_present(self):
        import os
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "..", "migrations", "versions", "20260504_0001_add_trgm_search_index.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        assert 'revision = "20260504_0001"' in source
        assert 'down_revision = "20260503_0002"' in source


class TestTrigramMigrationSQL:
    def test_creates_pg_trgm_extension(self):
        assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in _read_upgrade_source()

    def test_all_indexes_use_concurrently(self):
        count = _read_upgrade_source().count("CONCURRENTLY")
        assert count >= 4, f"Expected >= 4 CONCURRENTLY, got {count}"

    def test_uses_autocommit_block(self):
        import os
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "..", "migrations", "versions", "20260504_0001_add_trgm_search_index.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        assert "autocommit_block" in source

    def test_all_ilike_columns_indexed(self):
        src = _read_upgrade_source()
        assert "food_name gin_trgm_ops" in src
        assert "food_name_vi gin_trgm_ops" in src
        assert "food_name_en gin_trgm_ops" in src
        assert "category gin_trgm_ops" in src

    def test_uses_gin_not_gist(self):
        src = _read_upgrade_source()
        assert "USING GIN" in src
        assert "USING GIST" not in src

    def test_downgrade_drops_all_indexes(self):
        src = _read_downgrade_source()
        assert "idx_food_nutrition_name_trgm" in src
        assert "idx_food_nutrition_name_vi_trgm" in src
        assert "idx_food_nutrition_name_en_trgm" in src
        assert "idx_food_nutrition_category_trgm" in src
