"""Content-addressed readiness snapshots retain, but do not replace, owner decisions."""
from datetime import timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json

import pytest
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_readiness_receipt_store import SourceReadinessReceiptStore, canonical_snapshot
from aos_api.tenant_scope import TenantScope
from tests.test_data_fulfillment_store import Connection
from tests.test_source_readiness_investigation_projection import envelope, projection
from tests.aip._migration_test_support import isolated_aip_migration_database

SCOPE = TenantScope("org-org", "dev-project")


def test_nested_times_are_canonical_and_naive_times_are_rejected():
    item = envelope(investigation=projection())
    body, digest = canonical_snapshot(item)
    assert body["receiptRef"] is None
    assert body["sources"][0]["checkedAt"].endswith(".000000+00:00")
    shifted = item.model_copy(deep=True)
    shifted.sources[0].data_cutoff = shifted.sources[0].data_cutoff.astimezone(timezone(timedelta(hours=8)))
    assert canonical_snapshot(shifted) == (body, digest)
    shifted.sources[0].data_cutoff = shifted.sources[0].data_cutoff.replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone"):
        canonical_snapshot(shifted)


def test_put_and_exact_read_never_commit_or_invent_projection():
    item = envelope()
    body, digest = canonical_snapshot(item)
    conn = Connection({"authority": body, "content_hash": digest, "replayed": False})
    store = SourceReadinessReceiptStore(HostTransaction(conn), SCOPE)
    saved = store.put(item)
    assert saved.receipt_ref.resource_type == "SourceReadinessEnvelope"
    assert saved.receipt_ref.resource_id == "readiness-" + digest
    assert saved.receipt_ref.revision == "1"
    assert saved.investigation is None
    assert saved.receipt_ref.content_hash == digest
    assert store.read_exact(saved.receipt_ref) == saved
    assert conn.commits == 0
    assert all(sql.startswith("SELECT") for sql, _ in conn.calls)
    with pytest.raises(ValueError, match="receipt"):
        store.put(saved)


def test_store_rejects_scope_and_persisted_body_drift():
    item = envelope()
    body, digest = canonical_snapshot(item)
    conn = Connection({"authority": body, "content_hash": "0" * 64, "replayed": False})
    with pytest.raises(ValueError):
        SourceReadinessReceiptStore(HostTransaction(conn), SCOPE).put(item)
    conn.calls.clear()
    with pytest.raises(ValueError, match="tenant"):
        SourceReadinessReceiptStore(HostTransaction(conn), TenantScope("dev-org", "dev-project")).put(item)
    assert conn.calls == []


def test_isolated_postgres_content_replay_isolation_immutability_and_rollback():
    with isolated_aip_migration_database("ar2_source_readiness") as (_, dsn):
        @contextmanager
        def runtime(scope=SCOPE):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                yield conn, SourceReadinessReceiptStore(HostTransaction(conn), scope)

        item = envelope(investigation=projection())
        def save(_):
            with runtime() as (conn, store):
                result = store.put(item)
                conn.commit()
                return result
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, range(2)))
        assert results[0] == results[1]
        ref = results[0].receipt_ref
        with runtime() as (conn, store):
            assert store.read_exact(ref) == results[0]
            assert conn.execute("SELECT count(*) FROM source_readiness_receipt").fetchone()["count"] == 1
        with runtime(TenantScope("dev-org", "dev-project")) as (_, store):
            assert store.read_exact(ref) is None
        # Rollback is owned by the host, not by the snapshot Store.
        different = envelope()
        with runtime() as (conn, store):
            abandoned = store.put(different).receipt_ref
            conn.rollback()
        with runtime() as (_, store):
            assert store.read_exact(abandoned) is None
        body, digest = canonical_snapshot(item)
        for defect in ("hash", "tenant", "missing", "source", "status", "self_ref"):
            bad = deepcopy(body)
            if defect == "tenant": bad["tenant"]["orgId"] = "dev-org"
            if defect == "missing": bad.pop("checkedAt")
            if defect == "source": bad["sources"][0]["pipelineId"] = "another-source"
            if defect == "status": bad["status"] = "failed"
            if defect == "self_ref": bad["receiptRef"] = ref.model_dump(by_alias=True)
            bad_hash = hashlib.sha256(json.dumps(bad, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if defect == "hash": bad_hash = "0" * 64
            with runtime() as (conn, _):
                with pytest.raises(psycopg.Error) as error:
                    conn.execute("SELECT * FROM source_readiness_snapshot_put_ar2_009(%s,%s)", (Jsonb(bad), bad_hash))
                assert error.value.sqlstate == "SR001", defect
                conn.rollback()
        for statement in ("DELETE FROM source_readiness_receipt", "UPDATE source_readiness_receipt SET content_hash=content_hash", "TRUNCATE source_readiness_receipt"):
            with runtime() as (conn, _):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(statement)
                conn.rollback()
        # The SQL layer is not a second Python business schema evaluator.
        # A separately hashed malformed deep payload must never pass typed readback.
        malformed = deepcopy(body)
        malformed["sources"][0].pop("sourceId")
        malformed_hash = hashlib.sha256(json.dumps(malformed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with runtime() as (conn, _):
            conn.execute("SELECT * FROM source_readiness_snapshot_put_ar2_009(%s,%s)", (Jsonb(malformed), malformed_hash))
            conn.commit()
        malformed_ref = ref.model_copy(update={"resource_id": "readiness-" + malformed_hash, "content_hash": malformed_hash})
        with runtime() as (_, store):
            with pytest.raises(ValueError):
                store.read_exact(malformed_ref)
            assert store.put(item) == results[0]
        # Even owner updates cannot rewrite an accepted snapshot.
        with psycopg.connect(dsn) as conn:
            with pytest.raises(psycopg.Error) as error:
                conn.execute("UPDATE source_readiness_receipt SET authority=authority")
            assert error.value.sqlstate == "55000"
            conn.rollback()
