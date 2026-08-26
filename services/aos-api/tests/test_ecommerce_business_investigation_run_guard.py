"""BI-W4-03 single-active Run and triggerKey idempotency tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from unittest.mock import patch

from alembic import command
import psycopg
from psycopg.rows import dict_row
import pytest

from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunConflict,
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunStore,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw4_003_run_active_trigger_guard.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"


def _ref(identity: str) -> dict:
    return {
        "resourceType": "BusinessInvestigationCaseRevision",
        "resourceId": identity,
        "revision": 2,
        "contentHash": HASH_B,
    }


def _run(run_id: str, trigger_key: str, *, trigger_kind: str = "scheduled") -> BusinessInvestigationRunRecord:
    value = {
        "schemaVersion": "aos.ecommerce.business-investigation-run/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "runId": run_id,
        "version": 1,
        "contentHash": HASH_A,
        "caseRef": _ref("case-active"),
        "analysisType": "initial_store_analysis",
        "triggerKind": trigger_kind,
        "triggerKey": trigger_key,
        "lifecycle": "PREPARING",
        "control": "RUNNING",
        "createdBy": "business-owner",
        "createdAt": NOW,
    }
    draft = BusinessInvestigationRunRecord.model_validate(value)
    value["contentHash"] = draft.calculated_content_hash()
    return BusinessInvestigationRunRecord.model_validate(value)


def _migration():
    spec = util.spec_from_file_location("biw4_003", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_freezes_unique_slot_trigger_receipt_and_revokes_old_entrypoint() -> None:
    module = _migration()
    assert module.revision == "biw4_003" and module.down_revision == "biw4_002"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "PRIMARY KEY(org_id,project_id,case_id,analysis_type)" in sql
    assert "UNIQUE(org_id,project_id,case_id,analysis_type,trigger_key)" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "SKIPPED_OVERLAP" in sql
    assert "active Run overlap is not mergeable" in sql
    assert "REVOKE EXECUTE ON FUNCTION ecommerce_investigation_run_request_biw4_002" in sql
    assert "GRANT EXECUTE ON FUNCTION ecommerce_investigation_run_request_biw4_003" in sql
    assert sql.count("FORCE ROW LEVEL SECURITY") == 2
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw4_run_guard_empty") as (config, _dsn):
        command.downgrade(config, "biw4_002")
        command.upgrade(config, "head")


def test_trigger_replay_overlap_receipt_single_active_and_runtime_guard() -> None:
    with isolated_aip_migration_database("biw4_run_guard") as (_config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W4') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_case_head(org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,channel_id,business_entity_id) VALUES('org-org','dev-project','case-active',2,2,'ACTIVE','initial_store_analysis','private-mall','store-1')"
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,request_hash,authority_data,created_by,created_at) VALUES('org-org','dev-project','case-active',2,2,1,%s,'ACTIVE','initial_store_analysis','private-mall','store-1','binding-store-1','seed-active',%s,'{}','business-owner',NOW())",
                (HASH_B, HASH_A),
            )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn

        store = BusinessInvestigationRunStore(runtime_connect)
        created = store.request(SCOPE, _run("run-1", "scheduled:case-active:r1:t1"), idempotency_key="request-1")
        assert created.outcome == "CREATED" and not created.replayed and created.authority.run_id == "run-1"

        same_trigger = store.request(
            SCOPE,
            _run("run-2", "scheduled:case-active:r1:t1"),
            idempotency_key="different-request-id",
        )
        assert same_trigger.outcome == "CREATED" and same_trigger.replayed
        assert same_trigger.authority.run_id == "run-1"

        skipped = store.request(
            SCOPE,
            _run("run-3", "scheduled:case-active:r1:t2"),
            idempotency_key="request-overlap",
        )
        assert skipped.outcome == "SKIPPED_OVERLAP" and not skipped.replayed
        assert skipped.authority.run_id == "run-1"
        skipped_replay = store.request(
            SCOPE,
            _run("run-4", "scheduled:case-active:r1:t2"),
            idempotency_key="request-overlap-again",
        )
        assert skipped_replay.outcome == "SKIPPED_OVERLAP" and skipped_replay.replayed

        with pytest.raises(BusinessInvestigationRunConflict):
            store.request(
                SCOPE,
                _run("run-manual", "manual:case-active:2", trigger_kind="manual"),
                idempotency_key="request-manual-overlap",
            )

        with psycopg.connect(dsn) as conn:
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_run").fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_run_active_slot").fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_run_trigger_receipt").fetchone()[0] == 2
            assert conn.execute(
                "SELECT count(*) FROM ecommerce_investigation_run_trigger_receipt WHERE outcome='SKIPPED_OVERLAP'"
            ).fetchone()[0] == 1

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)"
            )
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_run_active_slot").fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO ecommerce_investigation_run_active_slot(org_id,project_id,case_id,analysis_type,run_id,trigger_kind,trigger_key,acquired_at) VALUES('dev-org','dev-project','case','initial_store_analysis','run','scheduled','trigger',NOW())"
                )
