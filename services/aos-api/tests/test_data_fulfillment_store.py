from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from importlib import util
from pathlib import Path
import json
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
from aos_api.business_investigation_shared_contracts import InvestigationExactRef

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
    assert conn.commits == 1 and "data_fulfillment_bind_ar2_008" in conn.calls[0][0]


def test_store_rejects_scope_actor_hash_and_noncanonical_artifact_before_db() -> None:
    conn = Connection(); store = DataFulfillmentStore(factory(conn))
    with pytest.raises(DataFulfillmentValidationError, match="tenant"): store.bind(SCOPE, "user:data-owner", "a", receipt(org="dev-org"))
    with pytest.raises(DataFulfillmentValidationError, match="actor"): store.bind(SCOPE, "user:other", "b", receipt())
    bad = receipt().model_copy(update={"content_hash": f"sha256:{'f' * 64}"})
    with pytest.raises(DataFulfillmentValidationError, match="content hash"): store.bind(SCOPE, "user:data-owner", "c", bad)
    with pytest.raises(Exception): receipt(kind="ExternalUrl")
    assert conn.calls == []


def fulfillment_row():
    item = receipt()
    return {
        "org_id": SCOPE.org_id, "project_id": SCOPE.project_id,
        "fulfillment_id": item.fulfillment_id, "receipt_id": item.receipt_id,
        "requirement_id": item.requirement_ref.resource_id,
        "requirement_revision": item.requirement_ref.revision,
        "requirement_hash": item.requirement_ref.content_hash[7:],
        "status": "fulfilled", "artifact_refs": [r.model_dump(by_alias=True) for r in item.artifact_refs],
        "source_readiness_ref": item.source_readiness_ref.model_dump(by_alias=True),
        "cutoff_at": item.cutoff_at, "fulfilled_at": item.fulfilled_at,
        "content_hash": item.content_hash[7:], "created_by": item.created_by,
        "authority_data": item.model_dump(by_alias=True, mode="json"),
    }


def fulfillment_ref():
    item = receipt()
    return InvestigationExactRef(resource_type="DataFulfillmentReceipt",
        resource_id=item.receipt_id, revision=1, content_hash=item.content_hash,
        receipt_id=item.receipt_id)


def test_exact_fulfillment_readback_uses_immutable_revision_and_no_write():
    conn = Connection(fulfillment_row())
    assert DataFulfillmentStore(factory(conn)).read_exact(SCOPE, fulfillment_ref()) == receipt()
    assert "JOIN data_requirement_revision" in conn.calls[0][0]
    assert "data_requirement_head" not in conn.calls[0][0]
    assert conn.commits == 0
    assert DataFulfillmentStore(factory(Connection())).read_exact(SCOPE, fulfillment_ref()) is None


@pytest.mark.parametrize("field,value", [
    ("org_id", "dev-org"), ("project_id", "another-project"),
    ("receipt_id", "another-receipt"), ("fulfillment_id", "another-fulfillment"),
    ("content_hash", "c" * 64), ("requirement_hash", "d" * 64),
    ("status", "partial"), ("status", "unknown"), ("status", "rejected"),
    ("authority_data", None),
])
def test_exact_fulfillment_readback_rejects_drift_and_incomplete_history(field, value):
    row = fulfillment_row()
    row[field] = value
    with pytest.raises(DataFulfillmentValidationError):
        DataFulfillmentStore(factory(Connection(row))).read_exact(SCOPE, fulfillment_ref())


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
        assert store.read_exact(SCOPE, fulfillment_ref()) == item
        assert store.read_exact(TenantScope("dev-org", "dev-project"), fulfillment_ref()) is None
        beijing = timezone(timedelta(hours=8))
        localized = item.model_copy(update={"receipt_id": "receipt-beijing", "fulfillment_id": "fulfillment-beijing",
            "cutoff_at": item.cutoff_at.astimezone(beijing), "fulfilled_at": item.fulfilled_at.astimezone(beijing)})
        localized = localized.model_copy(update={"content_hash": canonical_fulfillment_content_hash(localized)})
        store.bind(SCOPE, "user:data-owner", "bind-beijing", localized)
        localized_ref = InvestigationExactRef(resource_type="DataFulfillmentReceipt", resource_id=localized.receipt_id,
            revision=1, content_hash=localized.content_hash, receipt_id=localized.receipt_id)
        restored = store.read_exact(SCOPE, localized_ref)
        assert restored == localized
        assert restored.cutoff_at.utcoffset() == timedelta(hours=8)
        partial_payload = item.model_dump(by_alias=True)
        partial_payload.update(receiptId="receipt-partial", fulfillmentId="fulfillment-partial",
            status="partial", blockers=[{"code": "MISSING_DATA", "severity": "blocking",
            "dependency": "商品库存", "requiredAction": "补充库存后重新评估"}])
        partial = DataFulfillmentReceiptRecord.model_validate(partial_payload)
        partial = partial.model_copy(update={"content_hash": canonical_fulfillment_content_hash(partial)})
        store.bind(SCOPE, "user:data-owner", "bind-partial", partial)
        partial_ref = InvestigationExactRef(resource_type="DataFulfillmentReceipt", resource_id=partial.receipt_id,
            revision=1, content_hash=partial.content_hash, receipt_id=partial.receipt_id)
        assert store.read_exact(SCOPE, partial_ref) == partial
        versioned_payload = item.model_dump(by_alias=True)
        versioned_payload.update(receiptId="receipt-string-version", fulfillmentId="fulfillment-string-version")
        versioned_payload["artifactRefs"][0]["revision"] = "revision-v2"
        versioned_payload["sourceReadinessRef"]["revision"] = "readiness-v3"
        versioned = DataFulfillmentReceiptRecord.model_validate(versioned_payload)
        versioned = versioned.model_copy(update={"content_hash": canonical_fulfillment_content_hash(versioned)})
        store.bind(SCOPE, "user:data-owner", "bind-string-version", versioned)
        versioned_ref = InvestigationExactRef(resource_type="DataFulfillmentReceipt", resource_id=versioned.receipt_id,
            revision=1, content_hash=versioned.content_hash, receipt_id=versioned.receipt_id)
        assert store.read_exact(SCOPE, versioned_ref) == versioned
        from aos_api.data_fulfillment_store import _hash
        from psycopg.types.json import Jsonb
        for tamper in ("extra", "hash", "missing", "null_artifact", "missing_readiness",
                       "numeric_actor", "naive_time", "numeric_blocker", "duplicate_artifact",
                       "numeric_identity", "iso_time", "short_microseconds", "zero_microseconds", "missing_optional",
                       "tab_identity", "unicode_revision", "long_actor", "hour_24", "leap_second"):
            payload = json.loads(json.dumps(item.model_dump(by_alias=True, mode="python"), default=str))
            payload["receiptId"] = "invalid-receipt-" + tamper
            payload["fulfillmentId"] = "invalid-fulfillment-" + tamper
            if tamper == "extra": payload["unrecognized"] = True
            if tamper == "missing": payload.pop("receiptId")
            if tamper == "null_artifact": payload["artifactRefs"] = [None]
            if tamper == "missing_readiness": payload["sourceReadinessRef"].pop("revision")
            if tamper == "numeric_actor": payload["createdBy"] = 123
            if tamper == "naive_time": payload["cutoffAt"] = "2026-08-26 05:00:00"
            if tamper == "numeric_identity": payload["artifactRefs"][0]["resourceId"] = 123
            if tamper == "iso_time": payload["cutoffAt"] = "2026-08-26T05:00:00Z"
            if tamper == "short_microseconds": payload["cutoffAt"] = "2026-08-26 04:59:59.1+00:00"
            if tamper == "zero_microseconds": payload["cutoffAt"] = "2026-08-26 05:00:00.000000+00:00"
            if tamper == "missing_optional": payload["artifactRefs"][0].pop("receiptId")
            if tamper == "tab_identity": payload["artifactRefs"][0]["resourceId"] = "\tartifact-1"
            if tamper == "unicode_revision": payload["artifactRefs"][0]["revision"] = "\u3000v1"
            if tamper == "long_actor": payload["createdBy"] = " " + "a" * 200 + " "
            if tamper == "hour_24": payload["cutoffAt"] = "2026-08-25 24:00:00+00:00"
            if tamper == "leap_second": payload["cutoffAt"] = "2026-08-26 04:59:60+00:00"
            if tamper == "numeric_blocker":
                payload["status"] = "unknown"
                payload["blockers"] = [{"code": "MISSING_DATA", "severity": "blocking",
                                         "dependency": 123, "requiredAction": "重新读取"}]
            if tamper == "duplicate_artifact":
                payload["artifactRefs"].append({**payload["artifactRefs"][0], "receiptId": "different"})
            unsigned = {k: v for k, v in payload.items() if k != "contentHash"}
            payload["contentHash"] = "sha256:" + ("0" * 64 if tamper == "hash" else _hash(unsigned))
            with runtime_connect(SCOPE) as conn:
                with pytest.raises(psycopg.Error) as rejected:
                    conn.execute("SELECT * FROM data_fulfillment_bind_ar2_008(%s,%s,%s)",
                        (Jsonb(payload), "invalid-" + tamper, _hash({"operation": "fulfillment.bind", "receipt": payload})))
                conn.rollback()
                assert rejected.value.sqlstate == "DF001", tamper
                assert conn.execute("SELECT count(*) FROM data_fulfillment_receipt WHERE idempotency_key=%s",
                                    ("invalid-" + tamper,)).fetchone()["count"] == 0
        changed = item.model_copy(update={"fulfillment_id": "fulfillment-2"})
        changed = changed.model_copy(update={"content_hash": canonical_fulfillment_content_hash(changed)})
        with pytest.raises(DataFulfillmentIdempotencyConflict): store.bind(SCOPE, "user:data-owner", "bind-once", changed)
        with pytest.raises(DataFulfillmentConflict):
            store.bind(TenantScope(org_id="dev-org", project_id="dev-project"), "user:data-owner", "other-tenant", receipt(org="dev-org"))
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime"); conn.execute("SELECT set_config('aos.org_id','org-org',true)"); conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("INSERT INTO data_fulfillment_receipt(org_id,project_id,fulfillment_id,receipt_id,requirement_id,requirement_revision,status,artifact_refs,source_readiness_ref,cutoff_at,fulfilled_at,content_hash,created_by) VALUES('org-org','dev-project','manual','manual','requirement-1',1,'unknown','[]','{}',NOW(),NOW(),%s,'pytest')", ("c" * 64,))
