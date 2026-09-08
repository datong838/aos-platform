import importlib.util
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.ecommerce_growth_host_ports import (
    EcommerceGrowthHostBlocked,
    EcommerceGrowthHostConflict,
    EcommerceGrowthOperationBinding,
    LockedEcommerceGrowthHostPort,
)
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="dedicated database opt-in required",
)

PG = {"host": "127.0.0.1", "port": 18432, "user": "postgres", "dbname": "postgres"}


@pytest.fixture
def database():
    schema = "ar2_host_" + uuid4().hex
    host_role = "ar2_host_" + uuid4().hex[:16]
    owner = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_runtime = owner.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created_runtime:
        owner.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    owner.execute(sql.SQL("CREATE ROLE {} NOSUPERUSER NOBYPASSRLS NOLOGIN").format(sql.Identifier(host_role)))
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
        ):
            spec = importlib.util.spec_from_file_location(filename, root / "alembic/versions" / filename)
            migration = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(migration)
            migration.op = SimpleNamespace(execute=owner.execute)
            migration.upgrade()
        owner.execute(
            """CREATE TABLE host_test_authority(
                 org_id text NOT NULL,project_id text NOT NULL,operation_id text NOT NULL,active boolean NOT NULL,
                 PRIMARY KEY(org_id,project_id,operation_id))"""
        )
        owner.execute(
            """CREATE TABLE host_test_receipt(
                 org_id text NOT NULL,project_id text NOT NULL,receipt_id text NOT NULL,
                 PRIMARY KEY(org_id,project_id,receipt_id))"""
        )
        for table in ("host_test_authority", "host_test_receipt"):
            owner.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            owner.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            owner.execute(
                f"""CREATE POLICY tenant_scope ON {table}
                 USING(org_id=current_setting('aos.org_id',true)
                   AND project_id=current_setting('aos.project_id',true))
                 WITH CHECK(org_id=current_setting('aos.org_id',true)
                   AND project_id=current_setting('aos.project_id',true))"""
            )
        owner.execute(
            sql.SQL(
                "GRANT SELECT,UPDATE ON extension_operation_dispatch_binding,"
                "extension_runtime_binding TO {}"
            ).format(sql.Identifier(host_role))
        )
        owner.execute(
            sql.SQL("GRANT SELECT,INSERT ON host_test_receipt TO {}").format(sql.Identifier(host_role))
        )
        owner.execute(
            sql.SQL("GRANT SELECT ON host_test_authority TO {}").format(sql.Identifier(host_role))
        )
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            sql.Identifier(schema), sql.Identifier(host_role)
        ))
        yield SimpleNamespace(owner=owner, schema=schema, role=host_role)
    finally:
        owner.execute("RESET ROLE")
        owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(host_role)))
        if created_runtime:
            owner.execute("DROP ROLE aos_runtime")
        owner.close()


def _runtime_connection(database):
    @contextmanager
    def connection(scope):
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
    for operation_id in ("ecommerce_growth_case_put", "ecommerce_growth_schedule_put"):
        owner.execute(
            """INSERT INTO extension_operation_dispatch_binding(
                 org_id,project_id,operation_id,handler_kind,installation_id,generation,
                 execution_epoch,operation_fence,revision,cutover_group_id,cutover_group_revision,updated_by)
               VALUES(%s,%s,%s,'extension',%s,%s,3,false,5,%s,11,'test')""",
            (*scope.key, operation_id, installation, generation, group),
        )
    owner.execute(
        "INSERT INTO host_test_authority(org_id,project_id,operation_id,active) VALUES(%s,%s,%s,true)",
        (*scope.key, "ecommerce_growth_case_put"),
    )
    return SimpleNamespace(
        org_id=scope.org_id,
        project_id=scope.project_id,
        operation_id="ecommerce_growth_case_put",
        handler_kind="extension",
        dispatch_revision=5,
        installation_id=str(installation),
        generation=str(generation),
        execution_epoch=3,
        cutover_group_id=str(group),
        cutover_group_revision=11,
    )


def _receipt(receipt_id):
    return {
        "receiptRef": {
            "resourceType": "BusinessInvestigationCase",
            "resourceId": "case-qyh-001",
            "revision": 1,
            "contentHash": "sha256:" + "b" * 64,
            "receiptId": receipt_id,
        }
    }


def _binding(executor):
    def revalidate(*, transaction, scope, dispatch, **_):
        row = transaction.execute(
            """SELECT active FROM host_test_authority
                 WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
            (*scope.key, dispatch.operation_id),
        ).fetchone()
        if row is None or row["active"] is not True:
            raise EcommerceGrowthHostBlocked("business authority is not current")

    def verify_receipt(*, transaction, scope, receipt, **_):
        receipt_id = receipt["receiptRef"]["receiptId"]
        row = transaction.execute(
            """SELECT receipt_id FROM host_test_receipt
                 WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
            (*scope.key, receipt_id),
        ).fetchone()
        return {} if row is None else _receipt(row["receipt_id"])

    return EcommerceGrowthOperationBinding(
        operation_id="ecommerce_growth_case_put",
        receipt_keys=("receiptRef",),
        authority_kinds=("case",),
        revalidate=revalidate,
        execute=executor,
        verify_receipt=verify_receipt,
    )


def test_locked_host_commit_is_transactional_and_tenant_isolated(database):
    positive = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    positive_ref = _seed(database, positive)
    canary_ref = _seed(database, canary)

    def executor(*, transaction, scope, command, **_):
        transaction.execute(
            "INSERT INTO host_test_receipt(org_id,project_id,receipt_id) VALUES(%s,%s,%s)",
            (*scope.key, command["receiptId"]),
        )
        persisted = transaction.execute(
            "SELECT receipt_id FROM host_test_receipt WHERE receipt_id=%s",
            (command["receiptId"],),
        ).fetchone()
        return _receipt(persisted["receipt_id"])

    port = LockedEcommerceGrowthHostPort(
        {"ecommerce_growth_case_put": _binding(executor)},
        connect_factory=_runtime_connection(database),
    )
    assert port.commit(dispatch_ref=positive_ref, command={"receiptId": "positive-1"}) == _receipt("positive-1")
    assert port.commit(dispatch_ref=canary_ref, command={"receiptId": "canary-1"}) == _receipt("canary-1")

    with _runtime_connection(database)(positive) as conn:
        rows = conn.execute("SELECT receipt_id FROM host_test_receipt ORDER BY receipt_id").fetchall()
        assert rows == [{"receipt_id": "positive-1"}]
    with _runtime_connection(database)(canary) as conn:
        rows = conn.execute("SELECT receipt_id FROM host_test_receipt ORDER BY receipt_id").fetchall()
        assert rows == [{"receipt_id": "canary-1"}]


def test_locked_host_rolls_back_invalid_receipt_and_fails_closed_on_group_drift(database):
    scope = TenantScope("org-org", "dev-project")
    ref = _seed(database, scope)

    def invalid_executor(*, transaction, scope, **_):
        transaction.execute(
            "INSERT INTO host_test_receipt(org_id,project_id,receipt_id) VALUES(%s,%s,'must-rollback')",
            scope.key,
        )
        return {"receiptRef": {"resourceType": "Case"}}

    port = LockedEcommerceGrowthHostPort(
        {"ecommerce_growth_case_put": _binding(invalid_executor)},
        connect_factory=_runtime_connection(database),
    )
    with pytest.raises(EcommerceGrowthHostConflict):
        port.commit(dispatch_ref=ref, command={})
    assert database.owner.execute("SELECT count(*) AS count FROM host_test_receipt").fetchone()["count"] == 0

    database.owner.execute(
        """UPDATE extension_operation_dispatch_binding
              SET handler_kind='legacy',installation_id=NULL,generation=NULL,execution_epoch=NULL
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_schedule_put'""",
        scope.key,
    )
    with pytest.raises(EcommerceGrowthHostBlocked, match="cutover group"):
        port.commit(dispatch_ref=ref, command={})


def test_locked_host_rejects_inactive_authority_and_forged_receipt(database):
    scope = TenantScope("org-org", "dev-project")
    ref = _seed(database, scope)
    port = LockedEcommerceGrowthHostPort(
        {"ecommerce_growth_case_put": _binding(lambda **_: _receipt("not-persisted"))},
        connect_factory=_runtime_connection(database),
    )
    with pytest.raises(EcommerceGrowthHostConflict, match="readback drifted"):
        port.commit(dispatch_ref=ref, command={})

    database.owner.execute(
        "UPDATE host_test_authority SET active=false WHERE org_id=%s AND project_id=%s",
        scope.key,
    )
    with pytest.raises(EcommerceGrowthHostBlocked, match="business authority"):
        port.commit(dispatch_ref=ref, command={})
