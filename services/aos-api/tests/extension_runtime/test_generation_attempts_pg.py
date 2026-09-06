"""Generation attempt and drain authority on the dedicated PostgreSQL only."""
import importlib.util
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
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
                         owner_token="wrong-token-" + "w" * 32, state="failed")
    with conn.transaction():
        renewed = store.heartbeat(
            conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1, owner_token=TOKEN,
            lease_until=datetime.now(timezone.utc) + timedelta(minutes=2),
        )
    assert renewed.revision == 2
    with pytest.raises(RuntimeRevisionConflict):
        with conn.transaction():
            store.settle(conn, **SCOPE, attempt_id=lease.attempt_id, expected_revision=1,
                         owner_token=TOKEN, state="failed")


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
