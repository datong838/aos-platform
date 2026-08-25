"""Static W6-02 migration contract for tenant-scoped append-only profile authority."""

from importlib import util
from pathlib import Path
from unittest.mock import patch

MIGRATION = Path(__file__).parents[2] / "alembic" / "versions" / "w6_002_responsibility_profiles.py"


def _load():
    spec = util.spec_from_file_location("w6_002_responsibility_profiles", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_w6_002_extends_single_head_with_append_only_tenant_authority() -> None:
    module = _load()
    assert module.revision == "w6_002"
    assert module.down_revision == "w6_001"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    for table in (
        "aip_merge_policy_revision",
        "aip_profile_recommendation_revision",
        "aip_profile_confirmation_receipt",
        "aip_merge_decision_receipt",
    ):
        assert f"CREATE TABLE {table}" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
        assert f"GRANT SELECT, INSERT ON {table} TO aos_app" in sql
    assert "GRANT UPDATE" not in sql
    assert "GRANT DELETE" not in sql
    assert "ADD COLUMN profile_recommendation_ref JSONB" in sql
    assert "ADD COLUMN merge_decision_receipt_ids JSONB NOT NULL" in sql


def test_w6_002_downgrade_removes_only_its_additive_scope() -> None:
    module = _load()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    sql = "\n".join(statements)
    assert sql.index("DROP COLUMN IF EXISTS profile_recommendation_ref") < sql.index("DROP TABLE aip_merge_decision_receipt")
    assert sql.index("DROP TABLE aip_merge_decision_receipt") < sql.index("DROP TABLE aip_profile_confirmation_receipt")
    assert "DROP TABLE aip_responsibility_plan_revision" not in sql
