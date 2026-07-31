"""Alembic env — raw SQL migrations for AOS Platform.

Uses the same DATABASE_URL as aos_api.db (AOS_DATABASE_URL env var).
No SQLAlchemy models — all migrations use op.execute() with raw SQL.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

# Programmatic callers set sqlalchemy.url after validating migration mode and
# database state.  The environment variable remains available to the Alembic
# CLI, but must not overwrite the caller-supplied URL.
dsn = os.getenv("AOS_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if dsn.startswith("postgresql://"):
    dsn = "postgresql+psycopg://" + dsn.removeprefix("postgresql://")
elif dsn.startswith("postgres://"):
    dsn = "postgresql+psycopg://" + dsn.removeprefix("postgres://")
config.set_main_option("sqlalchemy.url", dsn.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No SQLAlchemy MetaData — all migrations use op.execute(raw_sql)
target_metadata = None


def run_migrations_offline() -> None:
    """Offline: emit SQL to stdout (no DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online: connect to real DB and run migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
