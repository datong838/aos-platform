from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from unittest.mock import patch

import pytest
import psycopg
from psycopg.rows import dict_row

from tests.aip._migration_test_support import isolated_aip_migration_database

from aos_api.data_fulfillment_store import (
    DataFulfillmentStore,
    DataFulfillmentConflict,
    DataFulfillmentIdempotencyConflict,
    DataFulfillmentValidationError,
    canonical_fulfillment_content_hash,
)
from aos_api.data_requirement_contracts import DataFulfillmentReceiptRecord
from aos_api.tenant_scope import TenantScope

MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw2_003_data_fulfillment_binding.py"
NOW = datetime(2026, 8, 26, 5, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
HASH = f"sha256:{'a' * 64}"


def ref(kind: str, identity: str, *, receipt: str | None = None):
    value = {"resourceType": kind, "resourceId": identity, "revision": 1, "contentHash": HASH}
    if receipt:
        value["receiptId"] = receipt
    return value


def receipt(*, org: str = "org-org", kind: str = "DataProductRevision"):
    raw = {
        "schemaVersion": "aos.data-fulfillment-authority-receipt/v1",
        "tenant": {"orgId": org, "projectId": "dev-project"},
        "fulfillmentId": "fulfillment-1", "receiptId": "receipt-1",
        "requirementRef": ref("DataRequirementRevision", "requirement-1"),
        "status": "fulfilled", "artifactRefs": [ref(kind, "artifact-1")],
        "sourceReadinessRef": ref("SourceReadinessEnvelope", "readiness-1", receipt="readiness-receipt-1"),
        "cutoffAt": NOW, "fulfilledAt": NOW, "contentHash": HASH,
        "createdBy": "user:data-owner", "blockers": [],
    }
    parsed = DataFulfillmentReceiptRecord.model_validate(raw)
    return parsed.model_copy(update={"content_hash": canonical_fulfillment_content_hash(parsed)})


def load_migration():
    spec = util.spec_from_file_location("biw2_003", MIGRATION); assert spec and spec.loader
    module = util.module_from_spec(spec); spec.loader.exec_module(module); return module


class Cursor:
    def __init__(self, row): self.row = row
    def fetchone(self): return self.row


class Connection:
    def __init__(self, row=None): self.row = row; self.calls = []; self.commits = 0
    def execute(self, sql, params=None): self.calls.append((" ".join(sql.split()), params)); return Cursor(self.row)
    def commit(self): self.commits += 1


def factory(connection):
    @contextmanager
    def connect(scope): assert scope == SCOPE; yield connection
    return connect


def test_migration_has_exact_current_idempotent_controlled_binding() -> None:
    module = load_migration(); assert module.revision == "biw2_003" and module.down_revision == "biw2_002"
    statements = []
    with patch.object(module.op, "execute", statements.append): module.upgrade()
    sql = "\n".join(statements)
    assert "data_fulfillment_bind_biw2_003" in sql and "SECURITY DEFINER" in sql
    assert "current_revision<>p_requirement_revision" in sql
    assert "current_content_hash<>p_requirement_hash" in sql
    assert "idempotency conflict" in sql and "pg_advisory_xact_lock" in sql
    assert "REVOKE INSERT ON data_fulfillment_receipt FROM aos_runtime" in sql
    assert "UPDATE data_requirement_head" not in sql


def test_store_binds_exact_receipt_and_returns_replay_state() -> None:
    item = receipt(); conn = Connection({"bound_receipt_id": "receipt-1", "result_content_hash": item.content_hash[7:], "replayed": False})
    result = DataFulfillmentStore(factory(conn)).bind(SCOPE, "user:data-owner", "bind-1", item)
    assert result.receipt_id == "receipt-1" and result.etag == item.content_hash and not result.replayed
    assert conn.commits == 1 and "data_fulfillment_bind_biw2_003" in conn.calls[0][0]


def test_store_rejects_scope_actor_hash_and_noncanonical_artifact_before_db() -> None:
    conn = Connection(); store = DataFulfillmentStore(factory(conn))
    with pytest.raises(DataFulfillmentValidationError, match="tenant"): store.bind(SCOPE, "user:data-owner", "a", receipt(org="dev-org"))
    with pytest.raises(DataFulfillmentValidationError, match="actor"): store.bind(SCOPE, "user:other", "b", receipt())
    bad = receipt().model_copy(update={"content_hash": f"sha256:{'f' * 64}"})
    with pytest.raises(DataFulfillmentValidationError, match="content hash"): store.bind(SCOPE, "user:data-owner", "c", bad)
    with pytest.raises(Exception): receipt(kind="ExternalUrl")
    assert conn.calls == []


def test_disposable_database_exact_replay_conflict_rls_and_direct_insert_denial() -> None:
    with isolated_aip_migration_database("biw2_fulfillment") as (_, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute("INSERT INTO data_requirement_head(org_id,project_id,requirement_id,current_revision,current_content_hash,status,version,created_by) VALUES('org-org','dev-project','requirement-1',1,%s,'accepted',1,'pytest')", ("a" * 64,))
            conn.execute("INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,revision,content_hash,status,operation,idempotency_key,request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by) VALUES('org-org','dev-project','requirement-1',1,%s,'accepted','request','seed',%s,'{}','{}','{}','{}','pytest')", ("a" * 64, "b" * 64))
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                yield conn

        store = DataFulfillmentStore(runtime_connect); item = receipt()
        first = store.bind(SCOPE, "user:data-owner", "bind-once", item)
        replay = store.bind(SCOPE, "user:data-owner", "bind-once", item)
        assert not first.replayed and replay.replayed
        changed = item.model_copy(update={"fulfillment_id": "fulfillment-2"})
        changed = changed.model_copy(update={"content_hash": canonical_fulfillment_content_hash(changed)})
        with pytest.raises(DataFulfillmentIdempotencyConflict): store.bind(SCOPE, "user:data-owner", "bind-once", changed)
        with pytest.raises(DataFulfillmentConflict):
            store.bind(TenantScope(org_id="dev-org", project_id="dev-project"), "user:data-owner", "other-tenant", receipt(org="dev-org"))
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime"); conn.execute("SELECT set_config('aos.org_id','org-org',true)"); conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("INSERT INTO data_fulfillment_receipt(org_id,project_id,fulfillment_id,receipt_id,requirement_id,requirement_revision,status,artifact_refs,source_readiness_ref,cutoff_at,fulfilled_at,content_hash,created_by) VALUES('org-org','dev-project','manual','manual','requirement-1',1,'unknown','[]','{}',NOW(),NOW(),%s,'pytest')", ("c" * 64,))
