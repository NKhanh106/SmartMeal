import os
import sys
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection

from alembic import context


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load .env.production if it exists (for alembic CLI running outside Docker)
_env = Path(__file__).resolve().parents[1] / ".env.production"
if _env.exists():
    load_dotenv(_env)


def _get_sync_database_url() -> str:
    """
    Build a synchronous database URL for Alembic migrations.

    Alembic CLI runs synchronously — it does NOT need asyncpg.
    Must use a sync driver (psycopg2 or bare postgresql://).

    Priority:
      1. MIGRATION_DATABASE_URL  (dedicated sync URL, e.g. postgresql://... direct)
      2. DATABASE_URL             (app async URL, converted to sync)

    Supabase notes:
      - Direct connection: port 5432 (no PgBouncer overhead)
      - Pooled connection:  port 6543 (for app runtime only)
      - SSL is mandatory
    """
    # Dedicated sync URL for migrations (preferred)
    raw_url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL", "")

    # Convert async driver to sync for alembic
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://")

    # Remove pgbouncer param (not valid on direct connection)
    url = url.replace("?pgbouncer=true", "")
    url = url.replace("&pgbouncer=true", "")

    # Ensure SSL for Supabase
    has_ssl_param = "sslmode" in url.lower() or "ssl=" in url.lower()
    if not has_ssl_param:
        sep = "&" if "?" in url else "?"
        url = url + sep + "sslmode=require"

    return url


config.set_main_option("sqlalchemy.url", _get_sync_database_url())

from app.models import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a sync connection."""
    from sqlalchemy import create_engine

    url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
