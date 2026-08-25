"""W7-08 disposable migration and downgrade safety contract."""
from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from tests.aip._migration_test_support import isolated_aip_migration_database


TABLES = {
    "aip_media_attempt_finance",
    "aip_media_attempt_finance_event",
    "aip_media_attempt_finance_idempotency",
}


def test_w7_08_migration_is_reversible_only_while_empty() -> None:
    with isolated_aip_migration_database("w708finance") as (config, dsn):
        engine = create_engine(dsn.replace("postgresql://", "postgresql+psycopg://", 1))
        try:
            assert TABLES <= set(inspect(engine).get_table_names())
            command.downgrade(config, "w7_005")
            assert TABLES.isdisjoint(inspect(engine).get_table_names())
            command.upgrade(config, "w7_006")
            assert TABLES <= set(inspect(engine).get_table_names())
        finally:
            engine.dispose()
