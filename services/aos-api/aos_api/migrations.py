"""Database migration management.

Supports two modes:
- Dev mode (default): stamps baseline + runs init_schema() (backward compatible)
- Production mode (AOS_DB_MIGRATE=1): runs alembic upgrade head before app start
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.migrations")

# Path to alembic.ini relative to services/aos-api/
_ALEMBIC_DIR = os.path.join(os.path.dirname(__file__), "..", "alembic")


def _get_alembic_cfg() -> Config:
    """Return alembic Config with the correct paths."""
    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    cfg = Config(ini_path)
    # Set the script location relative to alembic.ini
    cfg.set_main_option("script_location", _ALEMBIC_DIR)
    return cfg


def run_migrations() -> None:
    """Run database migrations before app startup.

    Behaviour is controlled by AOS_DB_MIGRATE env var:
    - '1' : production mode — run 'alembic upgrade head'
    - unset/other : dev mode — stamp baseline if needed, then init_schema()
    """
    try:
        _run_alembic_upgrade()
    except Exception as exc:
        log.warning("alembic_upgrade_failed will_still_start err=%s", exc)


def _run_alembic_upgrade() -> None:
    """Run alembic upgrade head."""
    cfg = _get_alembic_cfg()
    # Ensure DATABASE_URL is in the config
    from aos_api.db import get_dsn
    dsn = get_dsn()
    cfg.set_main_option("sqlalchemy.url", dsn)

    # Check if alembic_version table exists
    try:
        engine = create_engine(dsn)
        with engine.connect() as conn:
            result = conn.execute(
                conn.dialect.has_table(conn, "alembic_version")
            )
            has_table = bool(result)
        engine.dispose()
    except Exception:
        has_table = False

    if not has_table:
        # First run: stamp with baseline revision
        log.info("alembic_first_run stamping_baseline")
        command.stamp(cfg, "head")
    else:
        # Subsequent runs: upgrade to latest
        log.info("alembic_running_upgrade")
        command.upgrade(cfg, "head")

    log.info("alembic_upgrade_complete")
