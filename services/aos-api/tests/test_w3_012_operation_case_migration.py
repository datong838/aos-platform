from importlib import util
from pathlib import Path
from unittest.mock import patch


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "w3_012_operation_case_authority.py"
)


def _load():
    spec = util.spec_from_file_location("w3_012_operation_case_authority", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_extends_single_head_and_freezes_tenant_security() -> None:
    module = _load()
    assert module.revision == "w3_012"
    assert module.down_revision == "aip13_001"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    for table in module.TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
    for table in module.APPEND_ONLY_TABLES:
        assert f"trg_{table}_append_only" in sql
        assert f"REVOKE UPDATE,DELETE,TRUNCATE ON {table}" in sql


def test_downgrade_guards_canonical_history_before_reverse_drop() -> None:
    module = _load()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    assert "cannot downgrade w3_012" in statements[0]
    assert "ERRCODE = '55000'" in statements[0]
    drops = [statement for statement in statements if statement.startswith("DROP TABLE")]
    assert drops == [f"DROP TABLE IF EXISTS {table} CASCADE" for table in reversed(module.TABLES)]
