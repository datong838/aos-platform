from importlib import util
from pathlib import Path


MIGRATION = (Path(__file__).resolve().parents[2]
    / "alembic/versions/a0v_170_route_eval_release_material.py")


def load():
    spec = util.spec_from_file_location("a0v_170_route_eval_release_material", MIGRATION)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_route_release_material_is_scoped_hash_bound_and_immutable(monkeypatch):
    migration = load()
    statements = []
    monkeypatch.setattr(migration.op, "execute", statements.append)
    migration.upgrade()
    sql = "\n".join(statements)

    assert migration.revision == "a0v_170"
    assert migration.down_revision == "a0v_169"
    table = "aip_route_eval_release_material"
    assert "CREATE TABLE " + table in sql
    assert ("REFERENCES aip_route_eval_finalization_proof"
        "(org_id,project_id,execution_id)") in sql
    assert "UNIQUE(org_id,project_id,manifest_hash)" in sql
    assert "octet_length(manifest_payload) BETWEEN 1 AND 67108864" in sql
    assert "encode(digest(manifest_payload,'sha256'),'hex')=manifest_hash" in sql
    assert "ALTER TABLE " + table + " ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE " + table + " FORCE ROW LEVEL SECURITY" in sql
    assert "BEFORE UPDATE OR DELETE ON " + table in sql
    assert "BEFORE TRUNCATE ON " + table in sql
    assert "GRANT SELECT,INSERT ON " + table + " TO aos_route_eval_finalizer" in sql
    assert "GRANT SELECT ON " + table + " TO aos_runtime" in sql
    assert "GRANT aos_route_eval_finalizer TO" not in sql
    assert "INSERT INTO" not in sql


def test_route_release_material_refuses_destructive_downgrade():
    migration = load()
    try:
        migration.downgrade()
    except RuntimeError as exc:
        assert "reconciliation" in str(exc)
    else:
        raise AssertionError("Route release material cannot be silently dropped")
