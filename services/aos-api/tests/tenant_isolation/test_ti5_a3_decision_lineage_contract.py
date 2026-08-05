from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti5_a3_schema_report
from aos_api.tenant_scope import TenantScope

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti5a3_decision_lineage_contract.py"


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


def _ensure_scope(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s) "
            "ON CONFLICT (org_id,project_id) DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.commit()


def _insert_draft(scope: TenantScope, draft_id: str) -> None:
    with connect(scope) as conn:
        conn.execute(
            "INSERT INTO draft_dataset "
            "(id,action_type_id,object_type,object_id,created_by,org_id,project_id) "
            "VALUES (%s,'UpdateObject','WorkOrder','same-object','ti5-test',%s,%s)",
            (draft_id, *scope.key),
        )
        conn.commit()


def test_a3_migration_freezes_parent_evidence_and_contract() -> None:
    spec = importlib.util.spec_from_file_location("ti5a3_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti5a3lineage"
    assert module.down_revision == "228ti5a2kv"
    assert "ASSIGN_FROM_DRAFT" in source
    assert "decision_lineage_orphan_quarantine" in source
    assert "PRIMARY KEY (org_id,project_id,id)" in source
    assert "FORCE ROW LEVEL SECURITY" in source


def test_a3_schema_report_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti5_a3_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti5a3lineage",
        "228ti5b1models",
        "228ti6bcontract",
        "228ti6cassets",
    }
    assert report["ti5DecisionLineageScopeValid"] is True
    assert report["ti5DecisionLineagePrimaryKeyValid"] is True
    assert report["ti5DecisionLineageForeignKeysValid"] is True
    assert report["ti5DecisionLineageRlsValid"] is True
    assert report["ti5DecisionLineagePolicyValid"] is True
    assert report["ti5DecisionLineageParentOrphanCount"] == 0
    assert report["ti5DecisionLineageLedgerOrphanCount"] == 0


def test_a3_same_lineage_id_isolated_across_workspaces() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    draft_id = f"draft-{suffix}"
    lineage_id = f"lin-{draft_id}"
    for scope in (scope_a, scope_b):
        _ensure_scope(scope)
        _insert_draft(scope, draft_id)
        with connect(scope) as conn:
            conn.execute(
                "INSERT INTO decision_lineage "
                "(id,draft_id,action_type_id,object_type,object_id,steps,org_id,project_id) "
                "VALUES (%s,%s,'UpdateObject','WorkOrder','same-object','[]'::jsonb,%s,%s)",
                (lineage_id, draft_id, *scope.key),
            )
            conn.commit()

    with connect(scope_a) as conn:
        rows_a = conn.execute(
            "SELECT org_id,project_id FROM decision_lineage WHERE id=%s", (lineage_id,)
        ).fetchall()
    with connect(scope_b) as conn:
        rows_b = conn.execute(
            "SELECT org_id,project_id FROM decision_lineage WHERE id=%s", (lineage_id,)
        ).fetchall()
    assert [(row["org_id"], row["project_id"]) for row in rows_a] == [scope_a.key]
    assert [(row["org_id"], row["project_id"]) for row in rows_b] == [scope_b.key]

    for scope in (scope_a, scope_b):
        with connect(scope) as conn:
            conn.execute("DELETE FROM decision_lineage WHERE id=%s", (lineage_id,))
            conn.execute("DELETE FROM draft_dataset WHERE id=%s", (draft_id,))
            conn.commit()


def test_a3_no_scope_runtime_role_sees_no_lineage() -> None:
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert int(
            conn.execute("SELECT COUNT(*) AS n FROM decision_lineage").fetchone()["n"]
        ) == 0


def test_z_a3_downgrade_upgrade_preserves_lineage() -> None:
    cfg = _config()
    with connect() as conn:
        before = int(
            conn.execute("SELECT COUNT(*) AS n FROM decision_lineage").fetchone()["n"]
        )
    command.downgrade(cfg, "228ti5a2kv")
    with connect() as conn:
        assert int(
            conn.execute("SELECT COUNT(*) AS n FROM decision_lineage").fetchone()["n"]
        ) == before
        assert conn.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='decision_lineage' AND column_name='project_id'"
        ).fetchone() is None
    command.upgrade(cfg, "head")
    with connect() as conn:
        report = build_ti5_a3_schema_report(conn)
        assert int(
            conn.execute("SELECT COUNT(*) AS n FROM decision_lineage").fetchone()["n"]
        ) == before
    assert report["ok"] is True, report
