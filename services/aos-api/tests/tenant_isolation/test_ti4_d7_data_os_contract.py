from __future__ import annotations

import importlib.util
import inspect
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from aos_api import data_os_store as dos
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti4_d7_schema_report
from aos_api.tenant_scope import TenantScope
from psycopg.errors import ForeignKeyViolation, InsufficientPrivilege, RaiseException

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti4d7_data_os_contract.py"
TABLES = (
    "meta_source",
    "meta_pipeline",
    "meta_dataset",
    "meta_dataset_history",
    "meta_sync",
    "meta_schedule",
    "phase5_pipeline_graph",
)


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


def _ensure_workspace(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) "
            "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (scope.org_id, scope.project_id, scope.project_id),
        )
        conn.commit()


def _counts(conn) -> tuple[int, int]:
    active = sum(
        int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
        for table in TABLES
    )
    quarantine = int(
        conn.execute("SELECT COUNT(*) AS n FROM data_os_orphan_quarantine").fetchone()[
            "n"
        ]
    )
    return active, quarantine


def test_d7_migration_freezes_contract_and_runtime_has_no_schema_ddl() -> None:
    spec = importlib.util.spec_from_file_location("ti4d7_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti4d7contract"
    assert module.down_revision == "228ti4d6rls"
    assert tuple(module.SCOPED_PRIMARY_KEYS) == TABLES
    assert len(module.PARENT_FOREIGN_KEYS) == 6
    assert "data_os_orphan_quarantine" in source
    assert "guard_data_os_quarantine_immutable" in source
    assert "downgrade blocked by legacy key collision" in source
    runtime_schema_source = inspect.getsource(dos.ensure_data_os_schema)
    assert "CREATE TABLE" not in runtime_schema_source
    assert "ALTER TABLE" not in runtime_schema_source


def test_d7_schema_report_and_quarantine_guards_are_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti4_d7_schema_report(conn)
    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti4d7contract",
        "228ti4c3contract",
        "228ti4a1apollo",
    }
    assert report["ti4DataOsContractInvalidPrimaryKeys"] == []
    assert report["ti4DataOsContractNullableScope"] == []
    assert report["ti4DataOsContractInvalidParentForeignKeys"] == []
    assert report["ti4DataOsQuarantineExists"] is True
    assert report["ti4DataOsRuntimeQuarantineAccess"] is False
    assert report["ti4DataOsQuarantineGuardCount"] == 2
    assert report["ti4DataOsActiveNullScopeCount"] == 0

    scope = TenantScope("dev-org", "dev-project")
    with connect(scope) as conn:
        with pytest.raises(InsufficientPrivilege):
            conn.execute("SELECT 1 FROM data_os_orphan_quarantine")
        conn.rollback()
    with connect() as conn:
        conn.execute(
            "INSERT INTO data_os_orphan_quarantine "
            "(quarantine_id,source_table,source_key,payload,payload_hash,"
            "ownership_batch_id) VALUES "
            "('guard-test','meta_source','{}','{}','guard-test',%s)",
            (uuid.uuid4(),),
        )
        with pytest.raises(RaiseException):
            conn.execute(
                "UPDATE data_os_orphan_quarantine SET reason_code='changed' "
                "WHERE quarantine_id='guard-test'"
            )
        conn.rollback()


def test_d7_same_ids_coexist_and_cross_scope_parent_is_rejected() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    ids = {
        "source": f"source-{suffix}",
        "pipeline": f"pipeline-{suffix}",
        "dataset": f"dataset-{suffix}",
        "sync": f"sync-{suffix}",
        "schedule": f"schedule-{suffix}",
    }
    for scope, owner in ((scope_a, "A"), (scope_b, "B")):
        dos.persist_source(scope, {"id": ids["source"], "type": "file", "owner": owner})
        dos.persist_pipeline(
            scope,
            {
                "id": ids["pipeline"],
                "sourceId": ids["source"],
                "target": "dataset",
                "owner": owner,
            },
        )
        dos.persist_dataset(
            scope,
            {
                "rid": ids["dataset"],
                "name": owner,
                "sourceId": ids["source"],
                "pipelineId": ids["pipeline"],
            },
        )
        dos.persist_dataset_history(scope, ids["dataset"], [{"owner": owner}])
        dos.persist_sync(scope, {"id": ids["sync"], "sourceId": ids["source"]})
        dos.persist_schedule(
            scope, {"id": ids["schedule"], "pipelineId": ids["pipeline"]}
        )
        dos.persist_phase5_pipeline_graph(
            scope, {"pipeline_id": ids["pipeline"], "nodes": [], "edges": []}
        )

    assert dos.load_all(scope_a)["datasets"][ids["dataset"]]["name"] == "A"
    assert dos.load_all(scope_b)["datasets"][ids["dataset"]]["name"] == "B"

    b_only_source = f"b-only-{suffix}"
    dos.persist_source(scope_b, {"id": b_only_source, "type": "file"})
    with connect(scope_a) as conn:
        with pytest.raises(ForeignKeyViolation):
            conn.execute(
                "INSERT INTO meta_pipeline "
                "(id,source_id,org_id,project_id) VALUES (%s,%s,%s,%s)",
                (f"blocked-{suffix}", b_only_source, *scope_a.key),
            )
        conn.rollback()

    for scope in (scope_a, scope_b):
        dos.delete_phase5_pipeline_graph(scope, ids["pipeline"])
        dos.delete_schedule(scope, ids["schedule"])
        dos.delete_sync(scope, ids["sync"])
        dos.delete_dataset(scope, ids["dataset"])
        dos.delete_pipeline(scope, ids["pipeline"])
        dos.delete_source(scope, ids["source"])
    dos.delete_source(scope_b, b_only_source)


def test_z_d7_downgrade_upgrade_preserves_active_and_quarantine_counts() -> None:
    cfg = _config()
    with connect() as conn:
        before = _counts(conn)
    command.downgrade(cfg, "228ti4d6rls")
    with connect() as conn:
        active = sum(
            int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in TABLES
        )
        assert active == sum(before)
        assert conn.execute(
            "SELECT to_regclass('public.data_os_orphan_quarantine') AS name"
        ).fetchone()["name"] is None
    command.upgrade(cfg, "228ti4d7contract")
    with connect() as conn:
        assert _counts(conn) == before
    command.upgrade(cfg, "head")
