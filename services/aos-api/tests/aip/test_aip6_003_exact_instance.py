from pathlib import Path

from alembic import command
from alembic.config import Config

from aos_api.db import connect

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip6_003_agent_run_exact_instance.py"


def test_a6d_migration_adds_exact_instance_snapshots_without_secrets() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip6_003"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip6_002"' in text
    assert "instance_snapshot JSONB" in text
    assert "task_run_ref JSONB" in text
    assert "sender_instance_ref JSONB" in text
    assert "receiver_instance_ref JSONB" in text
    assert "api_key" not in text
    assert "bearer_token" not in text


def test_z_a6d_migration_downgrade_upgrade_is_independent() -> None:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.downgrade(config, "aip6_002")
    with connect() as conn:
        columns = conn.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_name IN ('aip_agent_run','aip_handoff_envelope')
                AND column_name IN ('instance_ref','instance_snapshot',
                  'sender_instance_ref','receiver_instance_ref','task_ref','task_run_ref')"""
        ).fetchall()
        assert columns == []
    command.upgrade(config, "head")
    with connect() as conn:
        columns = conn.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_name IN ('aip_agent_run','aip_handoff_envelope')
                AND column_name IN ('instance_ref','instance_snapshot',
                  'sender_instance_ref','receiver_instance_ref','task_ref','task_run_ref')"""
        ).fetchall()
        assert len(columns) == 8
