"""Real lock/CAS proof for the recoverable Store resource-lease fast path."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from test_generation_attempts_pg import attempt_case, database, pytestmark
from aos_api.extension_runtime.generation_attempts import PostgresRuntimeAttemptStore
from aos_api.extension_runtime.lease_renewal import _renew_live_recoverable_store
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
TOKEN = "lease-owner-" + "x" * 40
HASH = "sha256:" + "a" * 64


@contextmanager
def _connection(schema):
    with psycopg.connect(
        host="127.0.0.1", port=18432, user="postgres", dbname="postgres",
        autocommit=True, row_factory=dict_row,
    ) as conn:
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        conn.execute(
            "SELECT set_config('aos.org_id','org-org',false),"
            "set_config('aos.project_id','dev-project',false)"
        )
        yield conn


@pytest.fixture
def live_attempt(attempt_case):
    conn, installation, generation, _, schema = attempt_case
    operation = conn.execute(
        "SELECT operation_id FROM extension_runtime_operation WHERE installation_id=%s",
        (installation,),
    ).fetchone()[0]
    conn.execute(
        "UPDATE extension_runtime_operation SET status='succeeded',phase='succeeded',revision=3 "
        "WHERE operation_id=%s", (operation,),
    )
    resources = []
    proofs = []
    for index in range(3):
        resource_id = uuid4()
        container = (str(index + 1) * 64)[:64]
        package_hash = "sha256:" + str(index + 1) * 64
        conn.execute(
            """INSERT INTO extension_runtime_resource_lease
               (org_id,project_id,resource_id,operation_id,owner_token_ref,generation,
                package_id,package_hash,engine_context,resource_name,container_id,
                create_claimed_at,cleanup_state,expires_at,observed_release)
               VALUES('org-org','dev-project',%s,%s,'secret://owner',%s,%s,%s,
                      'colima-aos-extension',%s,%s,clock_timestamp(),'pending',
                      clock_timestamp()+interval '30 seconds',false)""",
            (resource_id, operation, generation, f"pkg-{index}", package_hash,
             f"aos-ext-lease-{index}-{resource_id.hex[:8]}", container),
        )
        resources.append(resource_id)
        proofs.append({
            "resourceId": str(resource_id), "containerId": container,
            "packageHash": package_hash, "claimsHash": HASH,
        })
    handle = {"preparationOperationId": str(operation), "resources": proofs}
    conn.execute(
        "UPDATE extension_runtime_binding SET resource_handle_ref=%s WHERE installation_id=%s",
        (Jsonb(handle), installation),
    )
    with conn.transaction():
        attempt = PostgresRuntimeAttemptStore().begin_recoverable_store(
            conn, **SCOPE, installation_id=installation, generation=generation,
            execution_epoch=1, operation_key="snapshot-group:lease",
            idempotency_key="snapshot-group:lease", request_hash=HASH,
            owner_token=TOKEN,
            lease_until=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
    return conn, schema, installation, generation, operation, tuple(resources), handle, attempt


def _renew(conn, installation, generation, operation, checked_at):
    return _renew_live_recoverable_store(
        conn, **SCOPE, installation_id=installation, operation_id=operation,
        generation=generation, health_checked_at=checked_at,
    )


def test_fast_path_does_not_wait_for_installation_or_binding_row_lock(live_attempt):
    conn, schema, installation, generation, operation, resources, _, _ = live_attempt
    with _connection(schema) as blocker, _connection(schema) as worker:
        blocker.execute("BEGIN")
        blocker.execute(
            "SELECT installation_id FROM bundle_installation WHERE installation_id=%s FOR UPDATE",
            (installation,),
        )
        blocker.execute(
            "SELECT installation_id FROM extension_runtime_binding WHERE installation_id=%s FOR UPDATE",
            (installation,),
        )
        checked_at = worker.execute("SELECT clock_timestamp() AS now").fetchone()["now"]

        def execute():
            with worker.transaction():
                return _renew(worker, installation, generation, operation, checked_at)

        with ThreadPoolExecutor(max_workers=1) as pool:
            expires = pool.submit(execute).result(timeout=2)
        blocker.execute("ROLLBACK")
    rows = conn.execute(
        "SELECT resource_id,expires_at FROM extension_runtime_resource_lease ORDER BY resource_id"
    ).fetchall()
    assert {row[0] for row in rows} == set(resources)
    assert all(row[1] == expires for row in rows)
    assert conn.execute(
        "SELECT count(*) FROM extension_runtime_event WHERE type='runtime_inflight_lease_renewed'"
    ).fetchone()[0] == 1


def test_statement_time_binding_drift_rolls_back_every_renewal_write(live_attempt):
    conn, schema, installation, generation, operation, _, _, _ = live_attempt
    before = conn.execute(
        "SELECT resource_id,expires_at FROM extension_runtime_resource_lease ORDER BY resource_id"
    ).fetchall()
    with _connection(schema) as worker:
        checked_at = worker.execute("SELECT clock_timestamp() AS now").fetchone()["now"]

        class DriftConnection:
            @property
            def info(self):
                return worker.info

            def execute(self, query, params=None):
                if query.strip().startswith("UPDATE extension_runtime_resource_lease"):
                    with _connection(schema) as drift:
                        drift.execute(
                            "UPDATE extension_runtime_binding SET revision=revision+1 "
                            "WHERE installation_id=%s", (installation,),
                        )
                return worker.execute(query, params)

        with pytest.raises(RuntimeConflict, match="expired before renewal commit"):
            with worker.transaction():
                _renew(
                    DriftConnection(), installation, generation, operation, checked_at,
                )
    assert conn.execute(
        "SELECT resource_id,expires_at FROM extension_runtime_resource_lease ORDER BY resource_id"
    ).fetchall() == before
    assert conn.execute(
        "SELECT count(*) FROM extension_runtime_event WHERE type='runtime_inflight_lease_renewed'"
    ).fetchone()[0] == 0
