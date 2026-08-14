from __future__ import annotations

from alembic import command
from alembic.config import Config

from aos_api.db import connect, get_dsn


def test_w2b_migration_downgrade_upgrade_roundtrip() -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", get_dsn())
    command.downgrade(config, "aip7_001")
    with connect() as conn:
        remaining = conn.execute(
            """SELECT COUNT(*) AS count FROM pg_class
            WHERE relname IN (
              'aip_eval_contract_head','aip_eval_contract_revision',
              'aip_responsibility_plan_head','aip_responsibility_plan_revision'
            )"""
        ).fetchone()
        assert remaining["count"] == 0
    command.upgrade(config, "w2_002")
    with connect() as conn:
        restored = conn.execute(
            """SELECT COUNT(*) AS count FROM pg_class
            WHERE relname IN (
              'aip_eval_contract_head','aip_eval_contract_revision',
              'aip_responsibility_plan_head','aip_responsibility_plan_revision'
            )"""
        ).fetchone()
        assert restored["count"] == 4
