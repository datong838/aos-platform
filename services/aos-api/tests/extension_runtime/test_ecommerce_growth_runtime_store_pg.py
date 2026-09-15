"""Dedicated PostgreSQL proof for AR2-7D exact invocation Receipts."""

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.ecommerce_growth_host_ports import EcommerceGrowthDispatchSnapshot, HostTransaction
from aos_api.ecommerce_growth_runtime_store import BoundEcommerceGrowthRuntimeStore
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="dedicated PostgreSQL opt-in required",
)
PG = {
    "host": os.getenv("AOS_EXTENSION_PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("AOS_EXTENSION_PG_PORT", "18432")),
    "user": os.getenv("AOS_EXTENSION_PG_USER", "postgres"),
    "dbname": os.getenv("AOS_EXTENSION_PG_DATABASE", "postgres"),
}
ROOT = Path(__file__).resolve().parents[2]
HASH = "sha256:" + "a" * 64
TARGET = {
    "resourceType": "BusinessInvestigationCaseRevision",
    "resourceId": "case-qyh-001",
    "revision": 1,
    "contentHash": HASH,
    "receiptId": "receipt-qyh-001",
}


def _migration(owner, filename):
    spec = importlib.util.spec_from_file_location(filename, ROOT / "alembic/versions" / filename)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=owner.execute)
    migration.upgrade()
    return migration


@pytest.fixture
def database():
    dbname = "ar2_runtime_" + uuid4().hex[:20]
    admin = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_runtime = admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created_runtime:
        admin.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    database_pg = {**PG, "dbname": dbname}
    owner = psycopg.connect(**database_pg, autocommit=True, row_factory=dict_row)
    try:
        owner.execute("CREATE TABLE bundle_installation(org_id text,project_id text,installation_id uuid,etag_version bigint NOT NULL DEFAULT 1,PRIMARY KEY(org_id,project_id,installation_id))")
        _migration(owner, "ar1_001_extension_runtime_authority.py")
        _migration(owner, "ar2_001_ecommerce_dispatch_authority.py")
        migration = _migration(owner, "ar2_005_ecommerce_growth_runtime.py")
        owner.execute("GRANT USAGE ON SCHEMA public TO aos_runtime")
        yield SimpleNamespace(owner=owner, pg=database_pg, migration=migration)
    finally:
        owner.close()
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
            (dbname,),
        )
        admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
        if created_runtime:
            admin.execute("DROP ROLE aos_runtime")
        admin.close()


def seed(database, scope):
    installation, generation, group = uuid4(), uuid4(), uuid4()
    database.owner.execute(
        "INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES(%s,%s,%s)",
        (*scope.key, installation),
    )
    database.owner.execute(
        """INSERT INTO extension_runtime_binding(
          org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
          profile_ref,execution_epoch,desired_state,observed_state,enabled,operation_fence,config_ref)
          VALUES(%s,%s,%s,%s,1,'{}','internal-python-v1',3,'enabled','ready',true,false,'{}')""",
        (*scope.key, installation, generation),
    )
    database.owner.execute(
        """INSERT INTO extension_operation_dispatch_binding(
          org_id,project_id,operation_id,handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_id,cutover_group_revision,updated_by)
          VALUES(%s,%s,'ecommerce_growth_case_put','extension',%s,%s,3,false,5,%s,11,'test')""",
        (*scope.key, installation, generation, group),
    )
    return EcommerceGrowthDispatchSnapshot(
        operation_id="ecommerce_growth_case_put",
        dispatch_revision=5,
        installation_id=installation,
        generation=generation,
        execution_epoch=3,
        cutover_group_id=group,
        cutover_group_revision=11,
        runtime_revision=1,
        checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
    )


@contextmanager
def bound(database, scope):
    conn = psycopg.connect(**database.pg, autocommit=False, row_factory=dict_row)
    try:
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
        yield BoundEcommerceGrowthRuntimeStore(HostTransaction(conn), scope), conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def put(store, dispatch, response=None):
    return store.put(
        operation_id=dispatch.operation_id,
        idempotency_key="case-qyh-001",
        request_hash=HASH,
        dispatch=dispatch,
        response=response or {"receiptRef": TARGET, "businessTitle": "栖月汇经营分析"},
        target_receipt_ref=TARGET,
        actor="ecommerce-growth-runtime",
        occurred_at=dispatch.checked_at,
    )


def concurrent_put(database, scope, dispatch, response=None):
    with bound(database, scope) as (store, _):
        return put(store, dispatch, response).replayed


def signaled_concurrent_put(database, scope, dispatch, started):
    with bound(database, scope) as (store, conn):
        conn.execute("SET LOCAL statement_timeout='4s'")
        started.set()
        return put(store, dispatch).replayed


def test_postgres_replay_isolation_drift_and_nonempty_downgrade(database):
    positive = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    positive_dispatch = seed(database, positive)
    seed(database, canary)
    with bound(database, positive) as (store, _):
        assert put(store, positive_dispatch).replayed is False
        assert put(store, positive_dispatch).replayed is True
        assert store.read(operation_id=positive_dispatch.operation_id, idempotency_key="case-qyh-001")["receiptRef"] == TARGET
        assert store.read_exact(
            operation_id=positive_dispatch.operation_id,
            receipt_ref=TARGET,
        )["receiptRef"] == TARGET
    with bound(database, canary) as (store, _):
        assert store.read(operation_id=positive_dispatch.operation_id, idempotency_key="case-qyh-001") is None
        assert store.read_exact(
            operation_id=positive_dispatch.operation_id,
            receipt_ref=TARGET,
        ) is None
    with bound(database, positive) as (store, _):
        with pytest.raises(psycopg.Error, match="drifted"):
            put(store, positive_dispatch, {"receiptRef": TARGET, "businessTitle": "另一份经营分析"})
    with pytest.raises(psycopg.Error, match="not empty"):
        database.migration.downgrade()


def test_postgres_concurrent_replay_and_drift_are_serialized(database):
    scope = TenantScope("org-org", "dev-project")
    dispatch = seed(database, scope)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(
            future.result()
            for future in (
                pool.submit(concurrent_put, database, scope, dispatch),
                pool.submit(concurrent_put, database, scope, dispatch),
            )
        )
    assert results == [False, True]

    drifted = {"receiptRef": TARGET, "businessTitle": "另一份经营分析"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (
            pool.submit(concurrent_put, database, scope, dispatch),
            pool.submit(concurrent_put, database, scope, dispatch, drifted),
        )
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except psycopg.Error as exc:
                outcomes.append(str(exc))
    assert outcomes.count(True) == 1
    assert sum("drifted" in str(item) for item in outcomes) == 1


def test_postgres_receipt_function_revalidates_exact_dispatch_and_runtime(database):
    scope = TenantScope("org-org", "dev-project")
    dispatch = seed(database, scope)

    other_installation, other_generation = uuid4(), uuid4()
    database.owner.execute(
        "INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES(%s,%s,%s)",
        (*scope.key, other_installation),
    )
    database.owner.execute(
        """INSERT INTO extension_runtime_binding(
          org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
          profile_ref,execution_epoch,desired_state,observed_state,enabled,operation_fence,config_ref)
          VALUES(%s,%s,%s,%s,1,'{}','internal-python-v1',3,'enabled','ready',true,false,'{}')""",
        (*scope.key, other_installation, other_generation),
    )
    cross_installation = EcommerceGrowthDispatchSnapshot(
        operation_id=dispatch.operation_id,
        dispatch_revision=dispatch.dispatch_revision,
        installation_id=other_installation,
        generation=other_generation,
        execution_epoch=dispatch.execution_epoch,
        cutover_group_id=dispatch.cutover_group_id,
        cutover_group_revision=dispatch.cutover_group_revision,
        runtime_revision=dispatch.runtime_revision,
        checked_at=dispatch.checked_at,
    )
    with bound(database, scope) as (store, _):
        with pytest.raises(psycopg.Error, match="dispatch authority drifted"):
            put(store, cross_installation)

    database.owner.execute(
        """UPDATE extension_operation_dispatch_binding SET operation_fence=true
             WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
        (*scope.key, dispatch.operation_id),
    )
    with bound(database, scope) as (store, _):
        with pytest.raises(psycopg.Error, match="dispatch authority drifted"):
            put(store, dispatch)
    database.owner.execute(
        """UPDATE extension_operation_dispatch_binding SET operation_fence=false
             WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
        (*scope.key, dispatch.operation_id),
    )

    for changed in (
        replace(dispatch, execution_epoch=2),
        replace(dispatch, dispatch_revision=4),
        replace(dispatch, runtime_revision=2),
    ):
        with bound(database, scope) as (store, _):
            with pytest.raises(psycopg.Error, match="drifted|not executable"):
                put(store, changed)

    database.owner.execute(
        """UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,
                  desired_state='disabled',observed_state='stopped',revision=revision+1
             WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
        (*scope.key, dispatch.installation_id, dispatch.generation),
    )
    disabled = replace(dispatch, runtime_revision=2)
    with bound(database, scope) as (store, _):
        with pytest.raises(psycopg.Error, match="not executable"):
            put(store, disabled)


def test_postgres_host_and_direct_receipt_paths_share_one_lock_order(database):
    scope = TenantScope("org-org", "dev-project")
    dispatch = seed(database, scope)
    host = psycopg.connect(**database.pg, autocommit=False, row_factory=dict_row)
    try:
        host.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
        host.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
        host.execute("SET LOCAL statement_timeout='4s'")
        host.execute(
            """SELECT 1 FROM extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",
            (*scope.key, dispatch.operation_id),
        )
        host.execute(
            """SELECT 1 FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                FOR UPDATE""",
            (*scope.key, dispatch.installation_id, dispatch.generation),
        )
        started = Event()
        with ThreadPoolExecutor(max_workers=1) as pool:
            direct = pool.submit(signaled_concurrent_put, database, scope, dispatch, started)
            assert started.wait(timeout=2)
            store = BoundEcommerceGrowthRuntimeStore(HostTransaction(host), scope)
            assert put(store, dispatch).replayed is False
            host.commit()
            assert direct.result(timeout=5) is True
    finally:
        host.rollback()
        host.close()


def test_event_control_journal_exact_replay_isolation_and_downgrade(database):
    database.owner.execute('GRANT INSERT,UPDATE,DELETE ON ecommerce_growth_runtime_command_receipt TO aos_runtime')
    migration = _migration(database.owner, 'a0v_058_event_runtime_receipt.py')
    positive = TenantScope('org-org', 'dev-project')
    canary = TenantScope('dev-org', 'dev-project')
    dispatch = seed(database, positive)
    database.owner.execute("UPDATE extension_operation_dispatch_binding SET operation_id='ecommerce_growth_event_control'")
    dispatch = replace(dispatch, operation_id='ecommerce_growth_event_control')
    with bound(database, positive) as (store, conn):
        assert put(store, dispatch).replayed is False
        assert put(store, dispatch).replayed is True
        assert conn.execute("SELECT has_table_privilege(current_user,'ecommerce_growth_runtime_command_receipt','INSERT') AS allowed").fetchone()['allowed'] is False
    with bound(database, canary) as (store, _):
        assert store.read(operation_id=dispatch.operation_id, idempotency_key='case-qyh-001') is None
    with pytest.raises(psycopg.Error, match='drifted'):
        with bound(database, positive) as (store, _):
            put(store, dispatch, {'receiptRef': TARGET, 'changed': True})
    with pytest.raises(psycopg.Error, match='not empty'):
        migration.downgrade()


def test_event_journal_empty_upgrade_downgrade_preserves_base(database):
    migration = _migration(database.owner, 'a0v_058_event_runtime_receipt.py')
    migration.downgrade()
    dispatch = seed(database, TenantScope('org-org', 'dev-project'))
    with bound(database, TenantScope('org-org', 'dev-project')) as (store, _):
        assert put(store, dispatch).replayed is False
