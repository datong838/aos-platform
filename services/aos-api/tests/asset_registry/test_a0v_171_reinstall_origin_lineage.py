from importlib import util
from pathlib import Path

import pytest


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/a0v_171_reinstall_origin_lineage.py"
)


def load_migration():
    spec = util.spec_from_file_location("a0v_171_reinstall_origin_lineage", MIGRATION)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def normalized(statements):
    return " ".join(" ".join(statement.split()) for statement in statements)


def test_revision_and_immutable_tenant_scoped_relation(monkeypatch):
    migration = load_migration()
    statements = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()
    sql = normalized(statements)

    assert migration.revision == "a0v_171"
    assert migration.down_revision == "a0v_170"
    assert "CREATE TABLE public.bundle_installation_reinstall_origin" in sql
    for column in (
        "org_id TEXT NOT NULL", "project_id TEXT NOT NULL",
        "target_installation_pk UUID NOT NULL", "target_revision BIGINT NOT NULL",
        "source_installation_pk UUID NOT NULL",
        "source_terminal_revision BIGINT NOT NULL",
        "source_lock_hash TEXT NOT NULL", "target_lock_hash TEXT NOT NULL",
        "actor TEXT NOT NULL", "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    ):
        assert column in sql
    assert "PRIMARY KEY (org_id, project_id, target_installation_pk, target_revision)" in sql
    assert "target_revision = 1" in sql
    assert "target_installation_pk <> source_installation_pk" in sql
    assert sql.count("REFERENCES public.bundle_installation_revision") == 2
    assert "REFERENCES public.meta_workspace(org_id, project_id) ON DELETE RESTRICT" in sql
    assert sql.count("ON DELETE RESTRICT") >= 3
    assert sql.count("^sha256:[0-9a-f]{64}$") == 2

    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY tenant_scope_bundle_installation_reinstall_origin_a0v171" in sql
    assert "TO aos_runtime" in sql
    assert "current_setting('aos.org_id', true)" in sql
    assert "current_setting('aos.project_id', true)" in sql
    assert "REVOKE ALL ON public.bundle_installation_reinstall_origin FROM PUBLIC, aos_runtime" in sql
    assert "GRANT SELECT, INSERT ON public.bundle_installation_reinstall_origin TO aos_runtime" in sql
    assert "GRANT UPDATE" not in sql and "GRANT DELETE" not in sql and "GRANT TRUNCATE" not in sql

    assert "BEFORE UPDATE OR DELETE ON public.bundle_installation_reinstall_origin" in sql
    assert "BEFORE TRUNCATE ON public.bundle_installation_reinstall_origin" in sql
    assert sql.count("EXECUTE FUNCTION public.guard_bundle_control_immutable()") == 2


def test_downgrade_is_fail_closed():
    migration = load_migration()
    with pytest.raises(RuntimeError, match="immutable reinstall origin"):
        migration.downgrade()
