from importlib import util
from pathlib import Path
from unittest.mock import patch


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "d0_after_001_aftersale_event_authority.py"
)


def _load():
    spec = util.spec_from_file_location("d0_after_001_aftersale_event_authority", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_extends_w3_head_with_append_only_tenant_authority() -> None:
    module = _load()
    assert module.revision == "d0_after_001"
    assert module.down_revision == "w3_012"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "CREATE TABLE ecommerce_aftersale_event" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "REVOKE UPDATE,DELETE,TRUNCATE" in sql
    assert "guard_aip4_append_only" in sql
    assert "payload" not in sql.lower()


def test_downgrade_refuses_to_drop_nonempty_canonical_originals() -> None:
    module = _load()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    assert "cannot downgrade d0_after_001" in statements[0]
    assert "ERRCODE = '55000'" in statements[0]
    assert statements[-1] == "DROP TABLE ecommerce_aftersale_event CASCADE"
