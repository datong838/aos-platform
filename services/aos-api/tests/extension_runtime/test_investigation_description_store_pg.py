"""PostgreSQL proof for immutable, tenant-scoped investigation descriptions."""

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_investigation_description_store import InvestigationDescriptionStore
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="dedicated PostgreSQL opt-in required",
)
PG = {"host": "127.0.0.1", "port": 18432, "user": "postgres", "dbname": "postgres"}
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)
REQUEST_HASH = "sha256:" + "a" * 64


@pytest.fixture
def database():
    dbname = "ar2_description_" + uuid4().hex[:16]
    admin = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_runtime = admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created_runtime:
        admin.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    database_pg = {**PG, "dbname": dbname}
    owner = psycopg.connect(**database_pg, autocommit=True, row_factory=dict_row)
    migration = None
    try:
        filename = "ar2_006_investigation_description_receipt.py"
        spec = importlib.util.spec_from_file_location(filename, ROOT / "alembic/versions" / filename)
        migration = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(migration)
        migration.op = SimpleNamespace(execute=owner.execute)
        migration.upgrade()
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


@contextmanager
def store_for(database, scope):
    conn = psycopg.connect(**database.pg, autocommit=False, row_factory=dict_row)
    try:
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
        yield InvestigationDescriptionStore(HostTransaction(conn), scope)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def authority(scope, key, *, title="经营实体生意探究准备说明"):
    from aos_api.ecommerce_investigation_description_store import deterministic_receipt_id

    return {
        "schemaVersion": "aos.ecommerce.investigation-description/v1",
        "receiptId": str(deterministic_receipt_id(scope, key)),
        "analysisType": "initial_store_analysis",
        "businessTitle": title,
        "caseCreatable": True,
        "selection": {"caseCreatable": True},
        "sourceReadiness": {"status": "ready", "sources": []},
        "checkedAt": NOW.isoformat(),
    }


def put(database, scope, key="describe-qyh-001", payload=None):
    with store_for(database, scope) as store:
        return store.put(
            idempotency_key=key,
            request_hash=REQUEST_HASH,
            authority=payload or authority(scope, key),
            created_at=NOW,
        )


def test_description_replay_rls_drift_and_nonempty_downgrade(database):
    positive = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    first = put(database, positive)
    assert first.replayed is False
    assert put(database, positive).replayed is True
    with store_for(database, positive) as store:
        with pytest.raises(TypeError, match="requires UUID"):
            store.read(first.receipt_ref["resourceId"])
        assert store.read(UUID(first.receipt_ref["resourceId"])).authority == first.authority
    with store_for(database, canary) as store:
        assert store.read(UUID(first.receipt_ref["resourceId"])) is None
    assert database.owner.execute(
        "SELECT has_table_privilege('aos_runtime','ecommerce_investigation_description_receipt','SELECT') AS allowed"
    ).fetchone()["allowed"]
    assert not database.owner.execute(
        "SELECT has_table_privilege('aos_runtime','ecommerce_investigation_description_receipt','INSERT') AS allowed"
    ).fetchone()["allowed"]
    with pytest.raises(psycopg.Error, match="drifted"):
        put(database, positive, payload=authority(positive, "describe-qyh-001", title="另一份说明"))
    with pytest.raises(psycopg.Error, match="not empty"):
        database.migration.downgrade()


def test_description_concurrent_first_write_is_serialized(database):
    scope = TenantScope("org-org", "dev-project")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(put, database, scope) for _ in range(2)]
        results = [future.result().replayed for future in futures]
    assert sorted(results) == [False, True]
