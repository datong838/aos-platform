from importlib import util
from pathlib import Path
from unittest.mock import patch


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "w4_001_evidence_governance_build.py"
)


def _load():
    spec = util.spec_from_file_location("w4_001_evidence_governance_build", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_makes_evidence_append_only_and_adds_tenant_revoke_authority() -> None:
    module = _load()
    assert module.revision == "w4_001"
    assert module.down_revision == "w3_013"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "REVOKE UPDATE,DELETE,TRUNCATE ON aip_evidence" in sql
    assert "trg_aip_evidence_append_only_w4_001" in sql
    assert "CREATE TABLE aip_evidence_revoke_event" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "guard_aip4_append_only" in sql


def test_downgrade_refuses_when_canonical_revocation_exists() -> None:
    module = _load()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    assert "cannot downgrade w4_001" in statements[0]
    assert "ERRCODE = '55000'" in statements[0]
    assert statements[-3:] == [
        "DROP TABLE aip_evidence_revoke_event CASCADE",
        "DROP TRIGGER trg_aip_evidence_append_only_w4_001 ON aip_evidence",
        "GRANT UPDATE,DELETE ON aip_evidence TO aos_runtime",
    ]
