"""BI-W4-02 BusinessInvestigationRun, Event and local Outbox tests."""

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
from pydantic import ValidationError

from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunConflict,
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunStore,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw4_002_business_investigation_run.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"


def ref(kind: str, identity: str, *, revision: int = 1, content_hash: str = HASH_A) -> dict:
    return {"resourceType": kind, "resourceId": identity, "revision": revision, "contentHash": content_hash}


def run_payload(**changes) -> dict:
    value = {
        "schemaVersion": "aos.ecommerce.business-investigation-run/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "runId": "run-1",
        "version": 1,
        "contentHash": HASH_A,
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-active", revision=2, content_hash=HASH_B),
        "analysisType": "initial_store_analysis",
        "triggerKind": "manual",
        "triggerKey": "manual-2026-08-26-1",
        "lifecycle": "PREPARING",
        "control": "RUNNING",
        "createdBy": "business-owner",
        "createdAt": NOW,
    }
    value.update(changes)
    item = BusinessInvestigationRunRecord.model_validate(value)
    value["contentHash"] = item.calculated_content_hash()
    return value


def _migration():
    spec = util.spec_from_file_location("biw4_002", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_contract_is_preparing_running_and_never_copies_taskrun_state() -> None:
    run = BusinessInvestigationRunRecord.model_validate(run_payload())
    assert run.lifecycle == "PREPARING" and run.control == "RUNNING"
    assert run.calculated_content_hash() == run.content_hash
    with pytest.raises(ValidationError):
        BusinessInvestigationRunRecord.model_validate(run_payload(lifecycle="COMPLETED"))
    with pytest.raises(ValidationError):
        BusinessInvestigationRunRecord.model_validate(run_payload(triggerKind="automatic_guess"))
    with pytest.raises(ValidationError, match="Extra inputs"):
        BusinessInvestigationRunRecord.model_validate(run_payload(taskRunStatus="SUCCEEDED"))


def test_migration_is_atomic_receipt_first_rls_and_no_delivery_claim() -> None:
    module = _migration()
    assert module.revision == "biw4_002" and module.down_revision == "biw4_001"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 4
    assert sql.count("FORCE ROW LEVEL SECURITY") == 4
    assert "RUN_REQUESTED" in sql and "PENDING" in sql
    assert "NO_AIP_TASKRUN" in sql and "NO_DELIVERY_CLAIM" in sql
    assert "current exact ACTIVE Case is required" in sql
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql


def test_store_uses_controlled_function_and_checks_content_hash() -> None:
    run = BusinessInvestigationRunRecord.model_validate(run_payload())

    class Cursor:
        def fetchone(self):
            return {
                "authority_data": run.model_dump(by_alias=True, mode="json"),
                "outcome": "CREATED",
                "replayed": False,
            }

    class Connection:
        commits = 0
        calls = []
        def execute(self, sql, params):
            self.calls.append((" ".join(sql.split()), params))
            return Cursor()
        def commit(self):
            self.commits += 1

    connection = Connection()

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    result = BusinessInvestigationRunStore(connect).request(SCOPE, run, idempotency_key="request-run-1")
    assert not result.replayed and result.outcome == "CREATED" and connection.commits == 1
    assert "ecommerce_investigation_run_request_biw4_003" in connection.calls[0][0]
    with pytest.raises(BusinessInvestigationRunConflict, match="content hash"):
        BusinessInvestigationRunStore(connect).request(
            SCOPE, run.model_copy(update={"content_hash": HASH_B}), idempotency_key="bad-hash"
        )


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw4_run_empty") as (config, _dsn):
        command.downgrade(config, "biw4_001")
        command.upgrade(config, "head")


def test_disposable_database_atomic_active_case_idempotency_isolation_and_guard() -> None:
    with isolated_aip_migration_database("biw4_run_authority") as (config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W4') ON CONFLICT DO NOTHING")
            conn.execute("INSERT INTO ecommerce_investigation_case_head(org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,channel_id,business_entity_id) VALUES('org-org','dev-project','case-active',2,2,'ACTIVE','initial_store_analysis','private-mall','store-1')")
            conn.execute("INSERT INTO ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,request_hash,authority_data,created_by,created_at) VALUES('org-org','dev-project','case-active',2,2,1,%s,'ACTIVE','initial_store_analysis','private-mall','store-1','binding-store-1','seed-active',%s,'{}','business-owner',NOW())", (HASH_B, HASH_A))
            conn.execute("INSERT INTO ecommerce_investigation_case_head(org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,channel_id,business_entity_id) VALUES('org-org','dev-project','case-draft',1,1,'DRAFT','initial_store_analysis','private-mall','store-1')")
            conn.execute("INSERT INTO ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,request_hash,authority_data,created_by,created_at) VALUES('org-org','dev-project','case-draft',1,1,NULL,%s,'DRAFT','initial_store_analysis','private-mall','store-1','binding-store-1','seed-draft',%s,'{}','business-owner',NOW())", (HASH_A, HASH_B))
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                yield conn

        run = BusinessInvestigationRunRecord.model_validate(run_payload())
        store = BusinessInvestigationRunStore(runtime_connect)
        assert not store.request(SCOPE, run, idempotency_key="request-run-1").replayed
        assert BusinessInvestigationRunStore(runtime_connect).request(
            SCOPE, run, idempotency_key="request-run-1"
        ).replayed
        with psycopg.connect(dsn) as conn:
            counts = [
                conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in (
                    "ecommerce_investigation_run",
                    "ecommerce_investigation_run_event",
                    "ecommerce_investigation_run_outbox",
                    "ecommerce_investigation_run_command_receipt",
                )
            ]
            assert counts == [1, 1, 1, 1]
            non_claims = conn.execute("SELECT payload->'nonClaims' FROM ecommerce_investigation_run_outbox").fetchone()[0]
            assert "NO_AIP_TASKRUN" in non_claims and "NO_DELIVERY_CLAIM" in non_claims
            event_hash, outbox_hash = conn.execute(
                "SELECT event.content_hash,outbox.payload#>>'{eventRef,contentHash}' FROM ecommerce_investigation_run_event event JOIN ecommerce_investigation_run_outbox outbox USING(org_id,project_id,event_id)"
            ).fetchone()
            assert event_hash == outbox_hash and event_hash.startswith("sha256:")

        draft_case_run = BusinessInvestigationRunRecord.model_validate(
            run_payload(
                runId="run-draft",
                triggerKey="manual-draft",
                caseRef=ref("BusinessInvestigationCaseRevision", "case-draft", content_hash=HASH_A),
            )
        )
        with pytest.raises(BusinessInvestigationRunConflict):
            store.request(SCOPE, draft_case_run, idempotency_key="request-draft")
        stale = BusinessInvestigationRunRecord.model_validate(
            run_payload(runId="run-stale", triggerKey="manual-stale", caseRef=ref("BusinessInvestigationCaseRevision", "case-active"))
        )
        with pytest.raises(BusinessInvestigationRunConflict):
            store.request(SCOPE, stale, idempotency_key="request-stale")

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)")
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_run").fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("INSERT INTO ecommerce_investigation_run_outbox(org_id,project_id,outbox_id,event_id,run_id,status,payload,created_at) VALUES('dev-org','dev-project','direct','missing','missing','PENDING','{}',NOW())")
        with pytest.raises(Exception, match="cannot downgrade biw4_006"):
            command.downgrade(config, "biw4_001")
