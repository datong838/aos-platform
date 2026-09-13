"""Dedicated PostgreSQL proof for RLS, concurrency and reconcile-only recovery."""

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.automation_occurrence_store import (
    AutomationOccurrenceConflict,
    AutomationOccurrenceNotReady,
    AutomationOccurrenceStore,
    ScheduleBinding,
)
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="dedicated database opt-in required",
)

PG = {
    "host": os.getenv("AOS_EXTENSION_PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("AOS_EXTENSION_PG_PORT", "18432")),
    "user": os.getenv("AOS_EXTENSION_PG_USER", "postgres"),
    "dbname": os.getenv("AOS_EXTENSION_PG_DATABASE", "postgres"),
}


@pytest.fixture
def database():
    schema = "ar2_occ_" + uuid4().hex
    owner = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_runtime = owner.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created_runtime:
        owner.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    try:
        owner.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        owner.execute(
            "CREATE TABLE bundle_installation(org_id text,project_id text,installation_id uuid,"
            "etag_version bigint NOT NULL DEFAULT 1,PRIMARY KEY(org_id,project_id,installation_id))"
        )
        root = Path(__file__).resolve().parents[2]
        for filename in (
            "ar1_001_extension_runtime_authority.py",
            "ar2_001_ecommerce_dispatch_authority.py",
            "ar2_002_automation_occurrence.py",
        ):
            spec = importlib.util.spec_from_file_location(filename, root / "alembic/versions" / filename)
            migration = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(migration)
            migration.op = SimpleNamespace(execute=owner.execute)
            migration.upgrade()
        owner.execute(
            """CREATE TABLE extension_dispatch_claim_gate(
                 org_id text NOT NULL,project_id text NOT NULL,cutover_group_id uuid NOT NULL,
                 claim_paused boolean NOT NULL,
                 PRIMARY KEY(org_id,project_id,cutover_group_id))"""
        )
        owner.execute("GRANT SELECT ON extension_dispatch_claim_gate TO aos_runtime")
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
        assert owner.execute(
            "SELECT has_table_privilege('aos_runtime','extension_operation_dispatch_binding','SELECT') AS allowed"
        ).fetchone()["allowed"]
        assert owner.execute(
            "SELECT NOT rolsuper AND NOT rolbypassrls AS safe FROM pg_roles WHERE rolname='aos_runtime'"
        ).fetchone()["safe"]
        yield SimpleNamespace(owner=owner, schema=schema, role="aos_runtime")
    finally:
        owner.execute("RESET ROLE")
        owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        if created_runtime:
            owner.execute("DROP ROLE aos_runtime")
        owner.close()


def _runtime_connection(database, scope):
    @contextmanager
    def connection(_scope):
        conn = psycopg.connect(**PG, autocommit=False, row_factory=dict_row)
        try:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(database.role)))
            conn.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    return connection


def _seed(database, scope):
    installation, generation, group = uuid4(), uuid4(), uuid4()
    owner = database.owner
    owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    owner.execute(
        "INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES(%s,%s,%s)",
        (*scope.key, installation),
    )
    owner.execute(
        """INSERT INTO extension_runtime_binding(
             org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
             profile_ref,execution_epoch,desired_state,observed_state,enabled,operation_fence,config_ref)
           VALUES(%s,%s,%s,%s,1,'{}','internal-python-v1',3,'enabled','ready',true,false,'{}')""",
        (*scope.key, installation, generation),
    )
    owner.execute(
        """INSERT INTO extension_operation_dispatch_binding(
             org_id,project_id,operation_id,handler_kind,installation_id,generation,
             execution_epoch,operation_fence,revision,cutover_group_id,cutover_group_revision,updated_by)
           VALUES(%s,%s,'ecommerce_growth_schedule_trigger','extension',%s,%s,3,false,1,%s,1,'test')""",
        (*scope.key, installation, generation, group),
    )
    return ScheduleBinding(
        policy_id="weekly-qyh",
        policy_revision=1,
        policy_hash="sha256:" + "b" * 64,
        operation_id="ecommerce_growth_schedule_trigger",
        installation_id=installation,
        generation=generation,
        execution_epoch=3,
        cadence="weekly",
        effective_from=datetime(2026, 9, 1, tzinfo=UTC),
        weekly_day=1,
        local_time="08:00",
        approved=True,
        enabled=True,
    )


def test_event_batch_atomic_replay_and_concurrency(database):
    scope = TenantScope("org-org", "dev-project")
    binding = replace(_seed(database, scope), cadence="event", weekly_day=None, local_time=None)
    store = AutomationOccurrenceStore(_runtime_connection(database, scope), schema=database.schema)
    store.put_binding(scope, binding)
    deadline = datetime(2026, 9, 13, tzinfo=UTC)
    events = [("source-1", deadline), ("source-2", deadline)]
    barrier = Barrier(2)
    def record():
        barrier.wait()
        return store.record_event_batch(scope, binding, events=events)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: record(), range(2)))
    assert sorted(sum(write.replayed for write in batch) for batch in results) == [0, 2]
    assert [r.occurrence_id for r in results[0]] == [r.occurrence_id for r in results[1]]
    with pytest.raises(AutomationOccurrenceConflict, match="replay drifted"):
        store.record_event_batch(scope, binding, events=[("must-rollback", deadline), ("source-2", deadline + timedelta(seconds=1))])
    assert database.owner.execute("SELECT count(*) AS n FROM automation_occurrence").fetchone()["n"] == 2
    assert database.owner.execute("SELECT count(*) AS n FROM automation_occurrence_outbox").fetchone()["n"] == 2
    assert database.owner.execute("SELECT watermark FROM automation_schedule_binding").fetchone()["watermark"] is None
    with pytest.raises(AutomationOccurrenceNotReady):
        store.record_event_batch(TenantScope("dev-org", "dev-project"), binding, events=[("wrong-tenant", deadline)])
    database.owner.execute("UPDATE automation_schedule_binding SET enabled=false")
    with pytest.raises(AutomationOccurrenceNotReady):
        store.record_event_batch(scope, binding, events=[("disabled", deadline)])


@pytest.mark.parametrize("kind", ["empty", "too_many", "duplicate", "blank", "naive", "non_string"])
def test_event_batch_invalid_input_has_no_writes(database, kind):
    scope = TenantScope("org-org", "dev-project")
    binding = replace(_seed(database, scope), cadence="event", weekly_day=None, local_time=None)
    store = AutomationOccurrenceStore(_runtime_connection(database, scope), schema=database.schema)
    store.put_binding(scope, binding)
    deadline = datetime(2026, 9, 13, tzinfo=UTC)
    events = {"empty": [], "too_many": [(str(i), deadline) for i in range(101)],
              "duplicate": [("same", deadline), ("same", deadline)], "blank": [(" ", deadline)],
              "naive": [("one", deadline.replace(tzinfo=None))], "non_string": [(None, deadline)]}[kind]
    with pytest.raises(ValueError):
        store.record_event_batch(scope, binding, events=events)
    assert database.owner.execute("SELECT count(*) AS n FROM automation_occurrence").fetchone()["n"] == 0


def test_occurrence_authority_rls_concurrency_and_reconcile_only(database):
    positive = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    binding = _seed(database, positive)
    canary_binding = _seed(database, canary)
    positive_store = AutomationOccurrenceStore(
        _runtime_connection(database, positive), schema=database.schema
    )
    canary_store = AutomationOccurrenceStore(
        _runtime_connection(database, canary), schema=database.schema
    )
    positive_store.put_binding(positive, binding)
    canary_store.put_binding(canary, canary_binding)
    scheduled_at = datetime(2026, 9, 7, tzinfo=UTC)

    barrier = Barrier(2)

    def concurrent_record():
        barrier.wait()
        return positive_store.record_scheduled(
            positive,
            binding,
            scheduled_at=scheduled_at,
            local_slot="2026-09-07T08:00+0800",
            deadline=scheduled_at + timedelta(days=1),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        writes = list(pool.map(lambda _: concurrent_record(), range(2)))
    assert sum(write.replayed for write in writes) == 1
    with pytest.raises(AutomationOccurrenceNotReady, match="authority drifted"):
        positive_store.record_scheduled(
            positive,
            replace(binding, policy_hash="sha256:" + "c" * 64),
            scheduled_at=scheduled_at + timedelta(days=1),
            local_slot="drifted",
            deadline=scheduled_at + timedelta(days=2),
        )
    database.owner.execute(
        "UPDATE automation_schedule_binding SET approved=false WHERE org_id=%s AND project_id=%s",
        positive.key,
    )
    with pytest.raises(AutomationOccurrenceNotReady, match="not executable"):
        positive_store.record_scheduled(
            positive, binding, scheduled_at=scheduled_at + timedelta(days=2), local_slot="disabled-slot",
            deadline=scheduled_at + timedelta(days=3)
        )
    database.owner.execute(
        "UPDATE automation_schedule_binding SET approved=true WHERE org_id=%s AND project_id=%s",
        positive.key,
    )

    with _runtime_connection(database, positive)(positive) as conn:
        assert conn.execute("SELECT count(*) AS count FROM automation_occurrence").fetchone()["count"] == 1
        assert conn.execute("SELECT count(*) AS count FROM automation_occurrence_outbox").fetchone()["count"] == 1
        assert not conn.execute(
            "SELECT has_table_privilege(current_user,'automation_occurrence','DELETE') AS allowed"
        ).fetchone()["allowed"]
        assert conn.execute(
            "SELECT has_table_privilege(current_user,'automation_occurrence','SELECT,INSERT,UPDATE') AS allowed"
        ).fetchone()["allowed"]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM automation_occurrence")
        conn.rollback()

    canary_store.record_scheduled(
        canary,
        canary_binding,
        scheduled_at=scheduled_at,
        local_slot="2026-09-07T08:00+0800",
        deadline=scheduled_at + timedelta(days=1),
    )
    with _runtime_connection(database, positive)(positive) as conn:
        assert conn.execute("SELECT count(*) AS count FROM automation_occurrence").fetchone()["count"] == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """INSERT INTO automation_occurrence(
                     org_id,project_id,occurrence_id,policy_id,policy_revision,policy_hash,operation_id,
                     installation_id,generation,execution_epoch,scheduled_at,local_slot,trigger_source,status,deadline)
                   VALUES('dev-org','dev-project',%s,'weekly-qyh',1,%s,%s,%s,%s,3,%s,'x','schedule','pending',%s)""",
                (uuid4(), binding.policy_hash, binding.operation_id, binding.installation_id,
                 binding.generation, scheduled_at + timedelta(days=7), scheduled_at + timedelta(days=8)),
            )
        conn.rollback()

    claimed = positive_store.claim_next(positive, owner="worker-a", now=scheduled_at)
    assert claimed is not None and claimed.target_idempotency_key.endswith(str(claimed.occurrence_id))
    database.owner.execute(
        "UPDATE automation_occurrence SET claim_until=%s WHERE org_id=%s AND project_id=%s AND occurrence_id=%s",
        (scheduled_at - timedelta(seconds=1), *positive.key, claimed.occurrence_id),
    )
    assert positive_store.claim_next(positive, owner="worker-b", now=scheduled_at) is None
    assert positive_store.reconcile_expired_claims(positive, now=scheduled_at) == 1
    with _runtime_connection(database, positive)(positive) as conn:
        assert conn.execute(
            "SELECT status FROM automation_occurrence WHERE occurrence_id=%s", (claimed.occurrence_id,)
        ).fetchone()["status"] == "needs_attention"
        assert conn.execute(
            "SELECT status FROM automation_occurrence_dispatch_attempt WHERE occurrence_id=%s",
            (claimed.occurrence_id,),
        ).fetchone()["status"] == "unknown"
    positive_store.reconcile_target_receipt(
        positive,
        occurrence_id=claimed.occurrence_id,
        receipt_ref={"receiptId": "target-found-after-crash"},
        occurred_at=scheduled_at,
    )
    with _runtime_connection(database, positive)(positive) as conn:
        assert conn.execute(
            "SELECT status FROM automation_occurrence WHERE occurrence_id=%s", (claimed.occurrence_id,)
        ).fetchone()["status"] == "accepted"

    event = positive_store.record_scheduled(
        positive, binding, scheduled_at=scheduled_at + timedelta(days=2), local_slot="receipt-expiry",
        deadline=scheduled_at + timedelta(days=3)
    )
    assert positive_store.claim_next(positive, owner="worker-early", now=scheduled_at) is None
    event_time = scheduled_at + timedelta(days=2)
    receipt_claim = positive_store.claim_next(positive, owner="worker-c", now=event_time)
    assert receipt_claim is not None and receipt_claim.occurrence_id == event.occurrence_id
    database.owner.execute(
        "UPDATE automation_occurrence SET claim_until=%s WHERE org_id=%s AND project_id=%s AND occurrence_id=%s",
        (event_time - timedelta(seconds=1), *positive.key, event.occurrence_id),
    )
    with pytest.raises(AutomationOccurrenceConflict, match="claim changed"):
        positive_store.record_target_receipt(
            positive,
            occurrence_id=event.occurrence_id,
            owner="worker-c",
            receipt_ref={"receiptId": "accepted-but-local-expired"},
            occurred_at=event_time,
        )
    assert positive_store.reconcile_expired_claims(positive, now=event_time) == 1

    water_barrier = Barrier(2)

    def advance(offset):
        water_barrier.wait()
        slot = scheduled_at + timedelta(days=7 + offset)
        try:
            positive_store.record_due_batch(
                positive,
                binding,
                expected_watermark=None,
                new_watermark=scheduled_at + timedelta(days=7),
                slots=[(slot, f"slot-{offset}", slot + timedelta(days=1), "pending")],
            )
            return "won"
        except AutomationOccurrenceConflict:
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(advance, (0, 1)))
    assert sorted(outcomes) == ["lost", "won"]
    with _runtime_connection(database, positive)(positive) as conn:
        assert conn.execute(
            "SELECT count(*) AS count FROM automation_occurrence WHERE local_slot LIKE 'slot-%'"
        ).fetchone()["count"] == 1
        assert conn.execute(
            """SELECT count(*) AS count FROM automation_occurrence_outbox x
               JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
               WHERE o.local_slot LIKE 'slot-%'"""
        ).fetchone()["count"] == 1


def test_schedule_binding_rollover_disables_old_revision_and_old_occurrence(database):
    scope = TenantScope("org-org", "dev-project")
    first = _seed(database, scope)
    store = AutomationOccurrenceStore(
        _runtime_connection(database, scope), schema=database.schema
    )
    store.put_binding(scope, first)
    scheduled_at = datetime(2026, 9, 7, tzinfo=UTC)
    store.record_scheduled(
        scope,
        first,
        scheduled_at=scheduled_at,
        local_slot="2026-09-07T08:00+0800",
        deadline=scheduled_at + timedelta(days=2),
    )
    second = replace(
        first,
        policy_revision=2,
        policy_hash="sha256:" + "c" * 64,
        effective_from=scheduled_at + timedelta(hours=1),
    )
    store.put_binding(scope, second)
    with _runtime_connection(database, scope)(scope) as conn:
        rows = conn.execute(
            """SELECT policy_revision,enabled FROM automation_schedule_binding
               WHERE policy_id=%s ORDER BY policy_revision""",
            (first.policy_id,),
        ).fetchall()
        assert rows == [
            {"policy_revision": 1, "enabled": False},
            {"policy_revision": 2, "enabled": True},
        ]
        conn.rollback()
    assert store.claim_next(
        scope, owner="rollover-test", now=scheduled_at + timedelta(hours=2)
    ) is None
    store.disable_policy_bindings(scope, first.policy_id)
    with _runtime_connection(database, scope)(scope) as conn:
        assert conn.execute(
            "SELECT count(*) AS count FROM automation_schedule_binding WHERE enabled"
        ).fetchone()["count"] == 0
        conn.rollback()


def test_expired_event_is_missed_and_replay_preserves_deadline(database):
    scope=TenantScope('org-org','dev-project')
    binding=replace(_seed(database,scope),cadence='event',weekly_day=None,local_time=None)
    store=AutomationOccurrenceStore(_runtime_connection(database,scope),schema=database.schema)
    store.put_binding(scope,binding)
    now=database.owner.execute('SELECT clock_timestamp() AS now').fetchone()['now'].replace(microsecond=0)
    deadline=now-timedelta(seconds=10)
    first=store.record_event(scope,binding,source_event_id='expired',deadline=deadline)
    replay=store.record_event(scope,binding,source_event_id='expired',deadline=deadline)
    assert first.status==replay.status=='missed'
    assert not first.replayed and replay.replayed
    assert first.occurrence_id==replay.occurrence_id
    row=database.owner.execute('SELECT deadline,status FROM automation_occurrence').fetchone()
    assert row==dict(deadline=deadline,status='missed')
    assert database.owner.execute('SELECT count(*) AS n FROM automation_occurrence_outbox').fetchone()['n']==1


def test_event_batch_records_mixed_current_and_expired_deadlines(database):
    scope=TenantScope('org-org','dev-project')
    binding=replace(_seed(database,scope),cadence='event',weekly_day=None,local_time=None)
    store=AutomationOccurrenceStore(_runtime_connection(database,scope),schema=database.schema)
    store.put_binding(scope,binding)
    now=database.owner.execute('SELECT clock_timestamp() AS now').fetchone()['now'].replace(microsecond=0)
    writes=store.record_event_batch(scope,binding,events=[('expired',now),('fresh',now+timedelta(hours=1))])
    assert [row.status for row in writes]==['missed','pending']
    assert database.owner.execute('SELECT count(*) AS n FROM automation_occurrence_outbox').fetchone()['n']==2
