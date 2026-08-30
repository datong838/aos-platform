import os

import psycopg
from alembic import command
from alembic.config import Config


def _config() -> Config:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    config = Config(os.path.join(root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(root, "alembic"))
    config.set_main_option("sqlalchemy.url", os.environ["AOS_DATABASE_URL"])
    return config


def _tables() -> set[str]:
    with psycopg.connect(os.environ["AOS_DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename LIKE 'aip_import_%' ORDER BY tablename"
        ).fetchall()
    return {row[0] for row in rows}


def test_aip_p4_import_job_migration_round_trip() -> None:
    config = _config()
    expected = {"aip_import_job", "aip_import_candidate", "aip_import_job_receipt"}
    assert expected <= _tables()

    command.downgrade(config, "aip_p3_002")
    assert expected.isdisjoint(_tables())

    command.upgrade(config, "head")
    assert expected <= _tables()
