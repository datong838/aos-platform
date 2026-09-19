"""Generation attempt and drain authority on the dedicated PostgreSQL only."""
import importlib.util
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import time
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from test_lifecycle_pg import database, seed, pytestmark

from aos_api.extension_runtime.generation_attempts import (
    ExpiredSignedReadAttemptRecovery,
    GenerationDrainReader,
    PostgresRuntimeAttemptStore,
)
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.extension_runtime.recoverable_store_attempt import RecoverableStoreAttemptOwner
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.tenant_scope import TenantScope

SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
TOKEN = "owner-token-" + "x" * 32
HASH = "sha256:" + "a" * 64


@pytest.fixture
def attempt_case(database):
    conn, role, schema = database
    path = Path(__file__).resolve().parents[2] / "alembic/versions/ar1_004_runtime_execution_attempt.py"
    spec = importlib.util.spec_from_file_location("ar1_attempt_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=conn.execute)
    migration.upgrade()
    for name in (
        "a0v_088_recoverable_store_attempt.py",
        "a0v_089_runtime_attempt_terminal_reason.py",
    ):
        path = Path(__file__).resolve().parents[2] / "alembic/versions" / name
        spec = importlib.util.spec_from_file_location("attempt_current_" + name, path)
        current = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(current)
        current.op = SimpleNamespace(execute=conn.execute)
        current.upgrade()
    conn.execute(sql.SQL("GRANT aos_runtime TO {}").format(sql.Identifier(role)))
    installation, _ = seed(conn)
    generation = uuid.uuid4()
    conn.execute(
        """INSERT INTO extension_runtime_binding
           (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
            profile_ref,config_ref,desired_state,observed_state,enabled,operation_fence)
           VALUES('org-org','dev-project',%s,%s,1,'{}','test','{}','enabled','ready',true,false)""",
        (installation, generation),
    )
    conn.execute(
        "SELECT set_config('aos.org_id','org-org',false),"
        "set_config('aos.project_id','dev-project',false)"
    )
    return conn, installation, generation, role, schema


@pytest.fixture
def recoverable_case(attempt_case):
    return attempt_case


@pytest.fixture
def terminal_reason_case(recoverable_case):
    return recoverable_case


def _begin(store, conn, installation, generation, **changes):
    args = dict(
        **SCOPE, installation_id=installation, generation=generation, execution_epoch=1,
        operation_kind="signed_read", operation_key="products.read",
        idempotency_key="read-once", request_hash=HASH, owner_token=TOKEN,
        lease_until=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    args.update(changes)
    with conn.transaction():
        return store.begin(conn, **args)


def _fence(conn):
    conn.execute(
        """UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,
           observed_state='draining',execution_epoch=2,revision=revision+1"""
    )


def test_begin_is_persistent_idempotent_and_never_regrants_execution(attempt_case):
    conn, installation, generation, _, _ = attempt_case
    store = PostgresRuntimeAttemptStore()
    first = _begin(store, conn, installation, generation)
    replay = _begin(store, conn, installation, generation, owner_token="different-" + "y" * 32)
    assert first.execute_once is True
    assert replay.attempt_id == first.attempt_id and replay.execute_once is False
    assert conn.execute("SELECT count(*) FROM extension_runtime_execution_attempt").fetchone() == (1,)
    assert conn.execute("SELECT type,state FROM extension_runtime_execution_attempt_event").fetchall() == [
        ("attempt_accepted", "running")
    ]
    with pytest.raises(RuntimeConflict, match="idempotency conflict"):
        _begin(store, conn, installation, generation, operation_key="other.read")


def test_fence_rejects_new_attempt_and_drain_waits_for_original_owner_settle(attempt_case):
    conn, installation, generation, _, _ = attempt_case
    store = PostgresRuntimeAttemptStore()
    lease = _begin(store, conn, installation, generation)
    _fence(conn)
    reader = GenerationDrainReader()
    with conn.transaction():
        assert reader(conn, **SCOPE, installation_id=installation, generation=generation, fence_epoch=2) is False
    with pytest.raises(PermissionError, match="not accepting"):
        _begin(store, conn, installation, generation, idempotency_key="after-fence")
    with conn.transaction():
        settled = store.settle(
            conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1,
            owner_token=TOKEN, state="succeeded",
        )
    assert settled.state == "succeeded" and settled.revision == 2
    with conn.transaction():
        assert reader(conn, **SCOPE, installation_id=installation, generation=generation, fence_epoch=2) is True


def test_expired_read_is_recovered_and_action_is_rejected(attempt_case):
    conn, installation, generation, _, _ = attempt_case
    store = PostgresRuntimeAttemptStore()
    read = _begin(
        store, conn, installation, generation,
        lease_until=datetime.now(timezone.utc) + timedelta(milliseconds=120),
    )
    with pytest.raises(ValueError, match="signed-read"):
        _begin(store, conn, installation, generation, operation_kind="action")
    conn.execute("SELECT pg_sleep(.15)")
    _fence(conn)
    with conn.transaction():
        abandoned = store.abandon_expired_reads(conn, **SCOPE)
    assert abandoned == (read.attempt_id,)
    with conn.transaction():
        assert GenerationDrainReader()(
            conn, **SCOPE, installation_id=installation, generation=generation, fence_epoch=2
        ) is True


def test_heartbeat_and_settle_require_exact_owner_and_revision(attempt_case):
    conn, installation, generation, _, _ = attempt_case
    store = PostgresRuntimeAttemptStore()
    lease = _begin(store, conn, installation, generation)
    with pytest.raises(PermissionError, match="token mismatch"):
        with conn.transaction():
            store.settle(conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1,
                         owner_token="wrong-token-" + "w" * 32, state="failed",
                         terminal_reason_code="RECOVERABLE_EXECUTION_EXCEPTION")
    with conn.transaction():
        renewed = store.heartbeat(
            conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1, owner_token=TOKEN,
            lease_until=datetime.now(timezone.utc) + timedelta(minutes=2),
        )
    assert renewed.revision == 2
    with pytest.raises(RuntimeRevisionConflict):
        with conn.transaction():
            store.settle(conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1,
                         owner_token=TOKEN, state="failed",
                         terminal_reason_code="RECOVERABLE_EXECUTION_EXCEPTION")


def test_recoverable_store_attempt_retries_only_after_terminal_failure(recoverable_case):
    conn, installation, generation, _, _ = recoverable_case
    store = PostgresRuntimeAttemptStore()
    args = dict(
        **SCOPE, installation_id=installation, generation=generation, execution_epoch=1,
        operation_key="snapshot-group:group-1", idempotency_key="snapshot-group:group-1",
        request_hash=HASH, owner_token=TOKEN,
        lease_until=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    with conn.transaction():
        first = store.begin_recoverable_store(conn, **args)
    assert first.execute_once is True and first.state == "running"
    with conn.transaction():
        active = store.begin_recoverable_store(
            conn, **{**args, "owner_token": "another-owner-" + "a" * 32}
        )
    assert active.attempt_id == first.attempt_id and active.execute_once is False
    with conn.transaction():
        store.settle(conn, **SCOPE, attempt_id=first.attempt_id, expected_revision=1,
                     owner_token=TOKEN, state="failed",
                     terminal_reason_code="RECOVERABLE_EXECUTION_EXCEPTION")
    with conn.transaction():
        second = store.begin_recoverable_store(conn, **args)
    assert second.execute_once is True and second.attempt_id != first.attempt_id
    assert conn.execute(
        "SELECT idempotency_key FROM extension_runtime_execution_attempt "
        "WHERE operation_kind='recoverable_store' ORDER BY accepted_at,attempt_id"
    ).fetchall() == [("snapshot-group:group-1:1",), ("snapshot-group:group-1:2",)]
    with conn.transaction():
        store.settle(conn, **SCOPE, attempt_id=second.attempt_id, expected_revision=1,
                     owner_token=TOKEN, state="succeeded")
    with conn.transaction():
        completed = store.begin_recoverable_store(conn, **args)
    assert completed.attempt_id == second.attempt_id and completed.execute_once is False


def test_recoverable_store_attempt_participates_in_fence_drain(recoverable_case):
    conn, installation, generation, _, _ = recoverable_case
    store = PostgresRuntimeAttemptStore()
    with conn.transaction():
        attempt = store.begin_recoverable_store(
            conn, **SCOPE, installation_id=installation, generation=generation,
            execution_epoch=1, operation_key="snapshot-group:group-2",
            idempotency_key="snapshot-group:group-2", request_hash=HASH,
            owner_token=TOKEN, lease_until=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
    _fence(conn)
    with conn.transaction():
        assert GenerationDrainReader()(
            conn, **SCOPE, installation_id=installation, generation=generation, fence_epoch=2
        ) is False
    with pytest.raises(PermissionError, match="not accepting"):
        with conn.transaction():
            store.begin_recoverable_store(
                conn, **SCOPE, installation_id=installation, generation=generation,
                execution_epoch=2, operation_key="snapshot-group:new",
                idempotency_key="snapshot-group:new", request_hash=HASH,
                owner_token=TOKEN,
                lease_until=datetime.now(timezone.utc) + timedelta(minutes=1),
            )
    with conn.transaction():
        store.settle(conn, **SCOPE, attempt_id=attempt.attempt_id, expected_revision=1,
                     owner_token=TOKEN, state="succeeded")
    with conn.transaction():
        assert GenerationDrainReader()(
            conn, **SCOPE, installation_id=installation, generation=generation, fence_epoch=2
        ) is True


def test_recoverable_store_owner_heartbeats_across_fence_then_settles(recoverable_case):
    conn, installation, generation, _, schema = recoverable_case
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))

    @contextmanager
    def connect():
        with psycopg.connect(
            host="127.0.0.1", port=18432, user="postgres", dbname="postgres",
            autocommit=True, row_factory=dict_row,
        ) as worker:
            worker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            worker.execute("SET SESSION AUTHORIZATION aos_runtime")
            yield worker

    scope = TenantScope("org-org", "dev-project")
    owner = RecoverableStoreAttemptOwner(
        connect=connect, heartbeat_seconds=.05, lease_seconds=.2,
    )
    with consumer_connection(connect, SCOPE) as worker:
        attempt = owner.claim(
            worker, scope=scope, installation_id=installation, generation=generation,
            execution_epoch=1, operation_key="snapshot-group:heartbeat",
            idempotency_key="snapshot-group:heartbeat", request_hash=HASH,
        )
    with attempt:
        time.sleep(.12)
        _fence(conn)
        with conn.transaction():
            assert GenerationDrainReader()(
                conn, **SCOPE, installation_id=installation,
                generation=generation, fence_epoch=2,
            ) is False
        time.sleep(.12)
    row = conn.execute(
        "SELECT state,revision,heartbeat_at IS NOT NULL FROM extension_runtime_execution_attempt "
        "WHERE attempt_id=%s", (attempt.attempt_id,),
    ).fetchone()
    assert row[0] == "succeeded" and row[1] >= 3 and row[2] is True
    with conn.transaction():
        assert GenerationDrainReader()(
            conn, **SCOPE, installation_id=installation, generation=generation, fence_epoch=2
        ) is True


def test_drain_rejects_unfenced_and_attempt_identity_is_immutable(attempt_case):
    conn, installation, generation, _, _ = attempt_case
    store = PostgresRuntimeAttemptStore()
    lease = _begin(store, conn, installation, generation)
    with pytest.raises(RuntimeConflict, match="expected fence"):
        with conn.transaction():
            GenerationDrainReader()(
                conn, **SCOPE, installation_id=installation, generation=generation, fence_epoch=2
            )
    with pytest.raises(psycopg.errors.RaiseException, match="identity is immutable"):
        conn.execute(
            "UPDATE extension_runtime_execution_attempt SET execution_epoch=2 WHERE attempt_id=%s",
            (lease.attempt_id,),
        )
    assert conn.execute(
        "SELECT execution_epoch,state,revision FROM extension_runtime_execution_attempt WHERE attempt_id=%s",
        (lease.attempt_id,),
    ).fetchone() == (1, "running", 1)


def test_attempt_events_are_append_only(attempt_case):
    conn, installation, generation, _, _ = attempt_case
    lease = _begin(PostgresRuntimeAttemptStore(), conn, installation, generation)
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        conn.execute(
            "UPDATE extension_runtime_execution_attempt_event SET state='failed' WHERE attempt_id=%s",
            (lease.attempt_id,),
        )
    with pytest.raises(psycopg.errors.RaiseException, match="does not match authority head"):
        conn.execute(
            """INSERT INTO extension_runtime_execution_attempt_event
               (org_id,project_id,attempt_id,sequence,event_id,type,state,revision)
               VALUES('org-org','dev-project',%s,2,%s,'attempt_failed','failed',2)""",
            (lease.attempt_id, uuid.uuid4()),
        )


def test_concurrent_same_idempotency_key_has_one_executor(attempt_case):
    conn, installation, generation, role, schema = attempt_case

    def begin_once(token):
        with psycopg.connect(host="127.0.0.1", port=18432, user="postgres", dbname="postgres", autocommit=True) as worker:
            worker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            worker.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            worker.execute(
                "SELECT set_config('aos.org_id','org-org',false),"
                "set_config('aos.project_id','dev-project',false)"
            )
            return _begin(
                PostgresRuntimeAttemptStore(), worker, installation, generation,
                owner_token=token,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(
            begin_once,
            ("concurrent-a-" + "a" * 32, "concurrent-b-" + "b" * 32),
        )
    assert {first.execute_once, second.execute_once} == {True, False}
    assert first.attempt_id == second.attempt_id
    assert conn.execute("SELECT count(*) FROM extension_runtime_execution_attempt").fetchone() == (1,)


def test_attempt_head_is_tenant_isolated_for_nonprivileged_role(attempt_case):
    conn, installation, generation, role, schema = attempt_case
    lease = _begin(PostgresRuntimeAttemptStore(), conn, installation, generation)
    with psycopg.connect(host="127.0.0.1", port=18432, user="postgres", dbname="postgres", autocommit=True) as reader:
        reader.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        reader.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        assert reader.execute("SELECT current_user").fetchone() == (role,)
        reader.execute(
            "SELECT set_config('aos.org_id','dev-org',false),"
            "set_config('aos.project_id','dev-project',false)"
        )
        assert reader.execute("SELECT attempt_id FROM extension_runtime_execution_attempt").fetchall() == []
        with pytest.raises(psycopg.errors.RaiseException, match="tenant scope mismatch"):
            with reader.transaction():
                reader.execute(
                    """INSERT INTO extension_runtime_execution_attempt
                       (org_id,project_id,attempt_id,installation_id,generation,execution_epoch,
                        operation_kind,operation_key,idempotency_key,request_hash,owner_token_hash,state,lease_until)
                       VALUES('org-org','dev-project',%s,%s,%s,1,'signed_read','forbidden.read',
                              'tenant-canary',%s,%s,'running',clock_timestamp()+interval '1 minute')""",
                    (uuid.uuid4(), installation, generation, HASH, HASH),
                )
        reader.execute("SELECT set_config('aos.org_id','org-org',false)")
        assert reader.execute("SELECT attempt_id FROM extension_runtime_execution_attempt").fetchall() == [
            (lease.attempt_id,)
        ]


def test_committed_attempt_survives_owner_exit_and_other_process_recovers_it(attempt_case):
    conn, installation, generation, role, schema = attempt_case

    # The production runtime role is intentionally fixed.  The isolated test
    # schema is created per case, so grant only schema visibility here; the
    # migration already owns the exact table privileges.
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))

    with psycopg.connect(
        host="127.0.0.1", port=18432, user="postgres", dbname="postgres", autocommit=True
    ) as owner:
        owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        owner.execute(
            "SELECT set_config('aos.org_id','org-org',false),"
            "set_config('aos.project_id','dev-project',false)"
        )
        lease = _begin(
            PostgresRuntimeAttemptStore(), owner, installation, generation,
            lease_until=datetime.now(timezone.utc) + timedelta(milliseconds=150),
        )

    _fence(conn)
    @contextmanager
    def recovery_connect():
        with psycopg.connect(
            host="127.0.0.1",
            port=18432,
            user="postgres",
            dbname="postgres",
            autocommit=True,
            row_factory=dict_row,
        ) as recovery:
            recovery.execute("SET SESSION AUTHORIZATION aos_runtime")
            recovery.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            recovery.execute(
                "SELECT set_config('aos.org_id','org-org',false),"
                "set_config('aos.project_id','dev-project',false)"
            )
            yield recovery

    attempt_recovery = ExpiredSignedReadAttemptRecovery(connect=recovery_connect)
    with recovery_connect() as recovery:
        with recovery.transaction():
            assert GenerationDrainReader()(
                recovery, **SCOPE, installation_id=installation,
                generation=generation, fence_epoch=2,
            ) is False
    # Process B cannot recover a still-live owner lease and never replays the read.
    assert attempt_recovery.run_once(**SCOPE) == ()
    conn.execute("SELECT pg_sleep(.18)")
    assert attempt_recovery.run_once(**SCOPE) == (lease.attempt_id,)
    with recovery_connect() as recovery:
        with recovery.transaction():
            assert GenerationDrainReader()(
                recovery, **SCOPE, installation_id=installation,
                generation=generation, fence_epoch=2,
            ) is True


def test_terminal_reason_is_atomic_bounded_and_matches_event(terminal_reason_case):
    conn, installation, generation, _, _ = terminal_reason_case
    store = PostgresRuntimeAttemptStore()
    lease = _begin(store, conn, installation, generation)
    with pytest.raises(ValueError, match="terminal reason"):
        with conn.transaction():
            store.settle(
                conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1,
                owner_token=TOKEN, state="failed",
            )
    with pytest.raises(ValueError, match="terminal reason"):
        with conn.transaction():
            store.settle(
                conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1,
                owner_token=TOKEN, state="failed", terminal_reason_code="RAW_FAILURE",
            )
    with conn.transaction():
        settled = store.settle(
            conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1,
            owner_token=TOKEN, state="failed",
            terminal_reason_code="RECOVERABLE_EXECUTION_EXCEPTION",
            terminal_error_type="IngressJournalConflict",
        )
    assert settled.state == "failed"
    assert conn.execute(
        "SELECT terminal_reason_code,terminal_error_type FROM extension_runtime_execution_attempt "
        "WHERE attempt_id=%s", (lease.attempt_id,),
    ).fetchone() == ("RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict")
    assert conn.execute(
        "SELECT terminal_reason_code,terminal_error_type FROM extension_runtime_execution_attempt_event "
        "WHERE attempt_id=%s ORDER BY sequence DESC LIMIT 1", (lease.attempt_id,),
    ).fetchone() == ("RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict")
    second = _begin(
        store, conn, installation, generation,
        idempotency_key="missing-reason", operation_key="missing-reason.read",
    )
    with pytest.raises(psycopg.errors.RaiseException, match="attempt failure"):
        conn.execute(
            "UPDATE extension_runtime_execution_attempt SET state='failed',revision=2,"
            "completed_at=clock_timestamp() WHERE attempt_id=%s", (second.attempt_id,),
        )


def test_recoverable_context_classifies_deadline_without_raw_message(terminal_reason_case):
    conn, installation, generation, _, schema = terminal_reason_case
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))

    @contextmanager
    def connect():
        with psycopg.connect(
            host="127.0.0.1", port=18432, user="postgres", dbname="postgres",
            autocommit=True, row_factory=dict_row,
        ) as worker:
            worker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            worker.execute("SET SESSION AUTHORIZATION aos_runtime")
            yield worker

    scope = TenantScope("org-org", "dev-project")
    owner = RecoverableStoreAttemptOwner(connect=connect, heartbeat_seconds=.05, lease_seconds=.2)
    with consumer_connection(connect, SCOPE) as worker:
        attempt = owner.claim(
            worker, scope=scope, installation_id=installation, generation=generation,
            execution_epoch=1, operation_key="snapshot-group:deadline",
            idempotency_key="snapshot-group:deadline", request_hash=HASH,
        )
    with pytest.raises(IngressJournalConflict, match="INGRESS_DEADLINE_EXCEEDED"):
        with attempt:
            raise IngressJournalConflict("INGRESS_DEADLINE_EXCEEDED")
    assert conn.execute(
        "SELECT state,terminal_reason_code,terminal_error_type "
        "FROM extension_runtime_execution_attempt WHERE attempt_id=%s", (attempt.attempt_id,),
    ).fetchone() == (
        "failed", "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict",
    )


def test_recoverable_context_stops_heartbeat_at_absolute_lifetime(terminal_reason_case):
    conn, installation, generation, _, schema = terminal_reason_case
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))

    @contextmanager
    def connect():
        with psycopg.connect(
            host="127.0.0.1", port=18432, user="postgres", dbname="postgres",
            autocommit=True, row_factory=dict_row,
        ) as worker:
            worker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            worker.execute("SET SESSION AUTHORIZATION aos_runtime")
            yield worker

    scope = TenantScope("org-org", "dev-project")
    owner = RecoverableStoreAttemptOwner(
        connect=connect, heartbeat_seconds=.05, lease_seconds=.2,
        max_execution_seconds=.12,
    )
    with consumer_connection(connect, SCOPE) as worker:
        attempt = owner.claim(
            worker, scope=scope, installation_id=installation, generation=generation,
            execution_epoch=1, operation_key="snapshot-group:absolute-deadline",
            idempotency_key="snapshot-group:absolute-deadline", request_hash=HASH,
        )
    with pytest.raises(RuntimeConflict, match="heartbeat failed"):
        with attempt:
            assert attempt.cancellation().wait(.5) is True
    assert conn.execute(
        "SELECT state,terminal_reason_code,terminal_error_type "
        "FROM extension_runtime_execution_attempt WHERE attempt_id=%s", (attempt.attempt_id,),
    ).fetchone() == (
        "failed", "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict",
    )


def test_expired_attempt_uses_fixed_terminal_reason(terminal_reason_case):
    conn, installation, generation, _, _ = terminal_reason_case
    lease = _begin(
        PostgresRuntimeAttemptStore(), conn, installation, generation,
        lease_until=datetime.now(timezone.utc) + timedelta(milliseconds=100),
    )
    conn.execute("SELECT pg_sleep(.12)")
    with conn.transaction():
        assert PostgresRuntimeAttemptStore().abandon_expired_reads(conn, **SCOPE) == (lease.attempt_id,)
    assert conn.execute(
        "SELECT state,terminal_reason_code,terminal_error_type "
        "FROM extension_runtime_execution_attempt WHERE attempt_id=%s", (lease.attempt_id,),
    ).fetchone() == ("abandoned", "ATTEMPT_LEASE_EXPIRED", None)


def test_a0v089_preserves_historical_terminal_rows_with_unknown_reason(database):
    conn, _, schema = database
    path = Path(__file__).resolve().parents[2] / "alembic/versions/ar1_004_runtime_execution_attempt.py"
    spec = importlib.util.spec_from_file_location("historical_attempt_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=conn.execute)
    migration.upgrade()
    installation, _ = seed(conn)
    generation = uuid.uuid4()
    attempt_id = uuid.uuid4()
    conn.execute(
        """INSERT INTO extension_runtime_binding
           (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
            profile_ref,config_ref,desired_state,observed_state,enabled,operation_fence)
           VALUES('org-org','dev-project',%s,%s,1,'{}','test','{}','enabled','ready',true,false)""",
        (installation, generation),
    )
    conn.execute(
        "SELECT set_config('aos.org_id','org-org',false),"
        "set_config('aos.project_id','dev-project',false)"
    )
    conn.execute(
        """INSERT INTO extension_runtime_execution_attempt
           (org_id,project_id,attempt_id,installation_id,generation,execution_epoch,
            operation_kind,operation_key,idempotency_key,request_hash,owner_token_hash,state,lease_until)
           VALUES('org-org','dev-project',%s,%s,%s,1,'signed_read','historical.read',
                  'historical',%s,%s,'running',clock_timestamp()+interval '1 minute')""",
        (attempt_id, installation, generation, HASH, HASH),
    )
    conn.execute(
        """INSERT INTO extension_runtime_execution_attempt_event
           (org_id,project_id,attempt_id,sequence,event_id,type,state,revision)
           VALUES('org-org','dev-project',%s,1,%s,'attempt_accepted','running',1)""",
        (attempt_id, uuid.uuid4()),
    )
    conn.execute(
        "UPDATE extension_runtime_execution_attempt SET state='failed',revision=2,"
        "completed_at=clock_timestamp() WHERE attempt_id=%s", (attempt_id,),
    )
    conn.execute(
        """INSERT INTO extension_runtime_execution_attempt_event
           (org_id,project_id,attempt_id,sequence,event_id,type,state,revision)
           VALUES('org-org','dev-project',%s,2,%s,'attempt_failed','failed',2)""",
        (attempt_id, uuid.uuid4()),
    )
    for name in (
        "a0v_088_recoverable_store_attempt.py",
        "a0v_089_runtime_attempt_terminal_reason.py",
    ):
        path = Path(__file__).resolve().parents[2] / "alembic/versions" / name
        spec = importlib.util.spec_from_file_location("historical_" + name, path)
        current = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(current)
        current.op = SimpleNamespace(execute=conn.execute)
        current.upgrade()
    assert conn.execute(
        "SELECT state,terminal_reason_code,terminal_error_type "
        "FROM extension_runtime_execution_attempt WHERE attempt_id=%s", (attempt_id,),
    ).fetchone() == ("failed", None, None)
    assert conn.execute(
        "SELECT state,terminal_reason_code,terminal_error_type "
        "FROM extension_runtime_execution_attempt_event WHERE attempt_id=%s AND sequence=2",
        (attempt_id,),
    ).fetchone() == ("failed", None, None)
