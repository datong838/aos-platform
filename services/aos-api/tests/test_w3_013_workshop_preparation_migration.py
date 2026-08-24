from importlib import util
from pathlib import Path
from unittest.mock import patch


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "w3_013_workshop_preparation.py"
)


def _load():
    spec = util.spec_from_file_location("w3_013_workshop_preparation", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_extends_single_head_with_tenant_intent_and_append_only_result() -> None:
    module = _load()
    assert module.revision == "w3_013"
    assert module.down_revision == "w3_011"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "CREATE TABLE aip_workshop_preparation_intent" in sql
    assert "CREATE TABLE aip_workshop_preparation_result" in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 2
    assert sql.count("FORCE ROW LEVEL SECURITY") == 2
    assert "UNIQUE(org_id,project_id,operation,idempotency_key)" in sql
    assert "guard_workshop_preparation_intent_w3_013" in sql
    assert "Workshop preparation intent identity is immutable" in sql
    assert "OLD.status='complete'" in sql
    assert "guard_aip4_append_only" in sql
    assert "REVOKE DELETE,TRUNCATE" in sql


def test_downgrade_refuses_to_drop_canonical_results() -> None:
    module = _load()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    assert "cannot downgrade w3_013" in statements[0]
    assert "ERRCODE = '55000'" in statements[0]
    assert statements[-3:] == [
        "DROP TABLE aip_workshop_preparation_result CASCADE",
        "DROP TABLE aip_workshop_preparation_intent CASCADE",
        "DROP FUNCTION guard_workshop_preparation_intent_w3_013()",
    ]
