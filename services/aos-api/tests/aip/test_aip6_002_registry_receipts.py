from pathlib import Path

from alembic import command
from alembic.config import Config

from aos_api.db import connect

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip6_002_registry_receipts.py"


def test_a6c_receipt_migration_is_linear_additive_and_secret_free() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip6_002"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip6_001"' in text
    assert "CREATE TABLE aip_agent_registry_receipt" in text
    assert "UNIQUE (org_id,project_id,operation,idempotency_key)" in text
    assert "GRANT SELECT ON aip_agent_template_revision TO aos_runtime" in text
    assert "GRANT SELECT ON aip_skill_template_revision TO aos_runtime" in text
    assert "api_key" not in text


def test_a6c_receipt_authority_is_scoped_and_append_only() -> None:
    with connect() as conn:
        row = conn.execute(
            """SELECT c.relrowsecurity,c.relforcerowsecurity
               FROM pg_class c WHERE c.relname='aip_agent_registry_receipt'"""
        ).fetchone()
        assert row["relrowsecurity"] and row["relforcerowsecurity"]
        triggers = conn.execute(
            """SELECT tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
               WHERE c.relname='aip_agent_registry_receipt' AND NOT t.tgisinternal"""
        ).fetchall()
        names = {row["tgname"] for row in triggers}
        assert "trg_aip_agent_registry_receipt_append_only" in names
        assert "trg_aip_agent_registry_receipt_truncate_guard" in names


def test_z_a6c_receipt_migration_downgrade_upgrade_is_independent() -> None:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    with connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM aip_agent_instance"
        ).fetchone()["n"]
    command.downgrade(config, "aip6_001")
    with connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM pg_class WHERE relname='aip_agent_registry_receipt'"
        ).fetchone()["n"] == 0
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM aip_agent_instance"
        ).fetchone()["n"] == before
    command.upgrade(config, "head")
    with connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM aip_agent_instance"
        ).fetchone()["n"] == before
