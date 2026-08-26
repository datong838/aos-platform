"""BI-W2-06 fenced DataRequirement Outbox delivery tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib import util
from pathlib import Path
from unittest.mock import patch

import pytest
import psycopg
from alembic import command
from psycopg.rows import dict_row

from aos_api.data_requirement_outbox_store import (
    DataRequirementOutboxConflict,
    DataRequirementOutboxStore,
    DataRequirementOutboxValidationError,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw2_004_data_requirement_outbox_delivery.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
NOW = datetime(2026, 8, 26, 6, 30, tzinfo=UTC)


def _load_migration():
    spec = util.spec_from_file_location("biw2_004", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.calls: list[tuple[str, object]] = []
        self.commits = 0

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return Cursor(next(self.rows))

    def commit(self):
        self.commits += 1


def factory(connection: Connection):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    return connect


def test_migration_is_additive_fenced_and_runtime_cannot_write_directly():
    module = _load_migration()
    assert module.revision == "biw2_004" and module.down_revision == "biw2_003"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "CREATE TABLE data_requirement_outbox_delivery" in sql
    assert "FOR UPDATE OF d SKIP LOCKED" in sql
    assert "SECURITY DEFINER" in sql
    assert "current_setting('aos.org_id',true)" in sql
    assert "state IN ('pending','claimed','acked','failed','unknown')" in sql
    assert "d.state='pending' OR (d.state='claimed' AND d.lease_expires_at<=NOW())" in sql
    assert "data_fulfillment_receipt" in sql and "r.status<>'unknown'" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql


def test_store_claim_and_ack_use_exact_fence_and_commit_once_each():
    claimed_row = {
        "outbox_id": "outbox-1",
        "requirement_id": "requirement-1",
        "requirement_revision": 1,
        "event_id": "event-1",
        "topic": "data.requirement.request",
        "payload": {"eventId": "event-1"},
        "content_hash": "a" * 64,
        "attempt": 1,
        "lease_token": "lease-token-1",
        "lease_expires_at": NOW + timedelta(minutes=5),
    }
    connection = Connection([claimed_row, {"state": "acked", "replayed": False}])
    store = DataRequirementOutboxStore(factory(connection))
    claim = store.claim_next(
        SCOPE,
        topic="data.requirement.request",
        worker_id="worker-1",
        lease_token="lease-token-1",
        lease_seconds=300,
    )
    assert claim and claim.outbox_id == "outbox-1" and claim.attempt == 1
    result = store.ack(SCOPE, "outbox-1", "lease-token-1")
    assert result.state == "acked" and result.replayed is False
    assert connection.commits == 2
    assert "data_requirement_outbox_claim_biw2_004" in connection.calls[0][0]
    assert "data_requirement_outbox_ack_biw2_004" in connection.calls[1][0]


def test_store_fails_closed_for_invalid_lease_and_stale_fence():
    untouched = Connection([])
    store = DataRequirementOutboxStore(factory(untouched))
    with pytest.raises(DataRequirementOutboxValidationError):
        store.claim_next(SCOPE, topic="", worker_id="worker-1", lease_token="token", lease_seconds=30)
    with pytest.raises(DataRequirementOutboxValidationError):
        store.claim_next(SCOPE, topic="topic", worker_id="worker-1", lease_token="token", lease_seconds=0)
    assert untouched.calls == []

    stale = Connection([None])
    with pytest.raises(DataRequirementOutboxConflict):
        DataRequirementOutboxStore(factory(stale)).ack(SCOPE, "outbox-1", "old-token")


def test_unknown_reconcile_requires_exact_non_unknown_receipt():
    connection = Connection(
        [
            {"state": "unknown", "replayed": False},
            {"state": "acked", "replayed": False},
        ]
    )
    store = DataRequirementOutboxStore(factory(connection))
    unknown = store.mark_unknown(SCOPE, "outbox-1", "lease-token-1", reason_code="DELIVERY_TIMEOUT")
    reconciled = store.reconcile_unknown(SCOPE, "outbox-1", "receipt-1")
    assert unknown.state == "unknown" and reconciled.state == "acked"
    assert "data_requirement_outbox_unknown_biw2_004" in connection.calls[0][0]
    assert "data_requirement_outbox_reconcile_biw2_004" in connection.calls[1][0]


def test_disposable_database_restart_fence_reconcile_isolation_and_downgrade():
    with isolated_aip_migration_database("biw2_outbox_delivery") as (config, dsn):
        command.downgrade(config, "biw2_003")
        command.upgrade(config, "head")
        with psycopg.connect(dsn) as conn:
            for org in ("org-org", "dev-org"):
                conn.execute(
                    "INSERT INTO data_requirement_head(org_id,project_id,requirement_id,current_revision,current_content_hash,status,version,created_by) VALUES(%s,'dev-project','requirement-1',1,%s,'accepted',1,'pytest')",
                    (org, "a" * 64),
                )
                conn.execute(
                    "INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,revision,content_hash,status,operation,idempotency_key,request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by) VALUES(%s,'dev-project','requirement-1',1,%s,'accepted','request','seed',%s,'{}','{}','{}','{}','pytest')",
                    (org, "a" * 64, "b" * 64),
                )
                conn.execute(
                    "INSERT INTO data_requirement_event(org_id,project_id,requirement_id,requirement_revision,event_id,sequence,event_type,to_status,payload,content_hash,created_by) VALUES(%s,'dev-project','requirement-1',1,'event-1',1,'requested','accepted','{}',%s,'pytest')",
                    (org, "a" * 64),
                )
                conn.execute(
                    "INSERT INTO data_requirement_outbox(org_id,project_id,outbox_id,requirement_id,requirement_revision,event_id,topic,payload,content_hash,created_by) VALUES(%s,'dev-project','outbox-1','requirement-1',1,'event-1','data.requirement.request','{}',%s,'pytest')",
                    (org, "a" * 64),
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

        store = DataRequirementOutboxStore(runtime_connect)
        first = store.claim_next(
            SCOPE,
            topic="data.requirement.request",
            worker_id="worker-1",
            lease_token="token-1",
            lease_seconds=300,
        )
        assert first and first.attempt == 1 and first.content_hash == f"sha256:{'a' * 64}"
        assert store.claim_next(
            SCOPE,
            topic="data.requirement.request",
            worker_id="worker-2",
            lease_token="token-busy",
            lease_seconds=300,
        ) is None
        with pytest.raises(DataRequirementOutboxConflict):
            store.ack(SCOPE, "outbox-1", "stale-token")

        with psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE data_requirement_outbox_delivery SET lease_expires_at=NOW()-INTERVAL '1 second' WHERE org_id='org-org' AND project_id='dev-project' AND outbox_id='outbox-1'"
            )
            conn.commit()
        recovered = store.claim_next(
            SCOPE,
            topic="data.requirement.request",
            worker_id="worker-restart",
            lease_token="token-2",
            lease_seconds=300,
        )
        assert recovered and recovered.attempt == 2
        unknown = store.mark_unknown(
            SCOPE, "outbox-1", "token-2", reason_code="DELIVERY_TIMEOUT"
        )
        assert unknown.state == "unknown"
        assert store.claim_next(
            SCOPE,
            topic="data.requirement.request",
            worker_id="worker-no-replay",
            lease_token="token-3",
            lease_seconds=300,
        ) is None
        with pytest.raises(DataRequirementOutboxConflict):
            store.reconcile_unknown(SCOPE, "outbox-1", "missing-receipt")

        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO data_fulfillment_receipt(org_id,project_id,fulfillment_id,receipt_id,requirement_id,requirement_revision,status,artifact_refs,source_readiness_ref,cutoff_at,fulfilled_at,content_hash,created_by) VALUES('org-org','dev-project','fulfillment-1','receipt-1','requirement-1',1,'fulfilled','[]','{}',NOW(),NOW(),%s,'pytest')",
                ("c" * 64,),
            )
            conn.commit()
        reconciled = store.reconcile_unknown(SCOPE, "outbox-1", "receipt-1")
        replay = store.reconcile_unknown(SCOPE, "outbox-1", "receipt-1")
        assert reconciled.state == "acked" and not reconciled.replayed and replay.replayed

        other = store.claim_next(
            TenantScope(org_id="dev-org", project_id="dev-project"),
            topic="data.requirement.request",
            worker_id="worker-other",
            lease_token="token-other",
            lease_seconds=300,
        )
        assert other and other.outbox_id == "outbox-1"
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','org-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO data_requirement_outbox_delivery(org_id,project_id,outbox_id) VALUES('org-org','dev-project','outbox-1')"
                )
