"""Only the dedicated ephemeral AR1-c database; never inherit application DSNs."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import psycopg
from psycopg import sql
import pytest

pytestmark = pytest.mark.skipif(os.getenv("AOS_EXTENSION_PG_TEST") != "1", reason="dedicated database opt-in required")


def test_registry_relation_rejects_expanded_or_custom_types(database):
    from aos_api.extension_runtime.storage_ports import require_registry_relation, StorageRoleDenied
    conn, _, schema = database
    conn.execute("CREATE TABLE products(id bigint, name text)")
    with conn.transaction():
        require_registry_relation(conn, table=schema+".products", column_types={"id":"int8","name":"text"})
    with pytest.raises(StorageRoleDenied):
        with conn.transaction():
            require_registry_relation(conn, table=schema+".products", column_types={"id":"text"})
    conn.execute("CREATE TABLE extra_products(extra text) INHERITS(products)")
    with pytest.raises(StorageRoleDenied):
        with conn.transaction():
            require_registry_relation(conn, table=schema+".products", column_types={"id":"int8"})
    conn.execute("CREATE DOMAIN custom_value AS bigint")
    conn.execute("CREATE TABLE custom_products(id custom_value)")
    with pytest.raises(StorageRoleDenied):
        with conn.transaction():
            require_registry_relation(conn, table=schema+".custom_products", column_types={"id":"int8"})


@pytest.fixture
def database():
    schema = "ar1c_" + uuid.uuid4().hex
    role = "ar1c_" + uuid.uuid4().hex
    conn = psycopg.connect(host="127.0.0.1", port=18432, user="postgres", dbname="postgres", autocommit=True)
    created_runtime=conn.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created_runtime:
        conn.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    try:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        # Exact referenced key shape only; full baseline integration is a separate test.
        conn.execute("CREATE TABLE bundle_installation(org_id text,project_id text,installation_id uuid,etag_version bigint NOT NULL DEFAULT 1,PRIMARY KEY(org_id,project_id,installation_id))")
        path = Path(__file__).resolve().parents[2] / "alembic/versions/ar1_001_extension_runtime_authority.py"
        spec=importlib.util.spec_from_file_location("ar1_test_migration",path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        migration.op=SimpleNamespace(execute=conn.execute)
        migration.upgrade()
        conn.execute(sql.SQL("CREATE ROLE {} NOSUPERUSER NOBYPASSRLS NOLOGIN").format(sql.Identifier(role)))
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema),sql.Identifier(role)))
        conn.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(sql.Identifier(schema),sql.Identifier(role)))
        yield conn,role,schema
    finally:
        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        if created_runtime:
            conn.execute("DROP ROLE aos_runtime")
        conn.close()


def seed(conn):
    installation=uuid.uuid4()
    conn.execute("INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES ('org-org','dev-project',%s)",(installation,))
    operation=uuid.uuid4()
    conn.execute("""INSERT INTO extension_runtime_operation
        (org_id,project_id,operation_id,installation_id,kind,idempotency_key,request_hash,
         requested_by,expected_installation_etag,status,phase,deadline)
        VALUES('org-org','dev-project',%s,%s,'runtime-apply','first',%s,'test-actor',1,'accepted','accepted',now()+interval '1 minute')""",
        (operation,installation,"sha256:"+"a"*64))
    return installation,operation


def test_real_rls_no_scope_and_negative_tenant(database):
    conn,role,_=database
    seed(conn)
    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
    assert conn.execute("SELECT count(*) FROM extension_runtime_operation").fetchone()[0]==0
    conn.execute("SELECT set_config('aos.org_id','dev-org',false),set_config('aos.project_id','dev-project',false)")
    assert conn.execute("SELECT count(*) FROM extension_runtime_operation").fetchone()[0]==0
    conn.execute("SELECT set_config('aos.org_id','org-org',false)")
    assert conn.execute("SELECT count(*) FROM extension_runtime_operation").fetchone()[0]==1


def test_real_event_is_append_only(database):
    conn,_,_=database
    _,operation=seed(conn)
    conn.execute("INSERT INTO extension_runtime_event VALUES('org-org','dev-project',%s,1,%s,'accepted','{}',%s,now())",
                 (operation,uuid.uuid4(),"sha256:"+"b"*64))
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("DELETE FROM extension_runtime_event")


def test_cross_tenant_fk_rejected(database):
    conn,_,_=database
    installation,_=seed(conn)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute("""INSERT INTO extension_audit_envelope
        (org_id,project_id,envelope_id,installation_id,business_title,envelope,source_receipt_ref)
        VALUES('dev-org','dev-project',%s,%s,'测试结果','{}','{}')""",(uuid.uuid4(),installation))


def test_cannot_enable_unready_binding(database):
    conn,_,_=database
    installation,_=seed(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("""INSERT INTO extension_runtime_binding
        (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,profile_ref,desired_state,observed_state,enabled)
        VALUES('org-org','dev-project',%s,%s,1,'{}','internal-python-v1','enabled','preparing',true)""",(installation,uuid.uuid4()))


def test_operation_replay_precedes_cas_and_conflicts_are_rejected(database):
    from datetime import datetime,timezone,timedelta
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore,RuntimeConflict,RuntimeRevisionConflict
    conn,_,_=database
    installation,_=seed(conn)
    store=RuntimeOperationStore()
    args=dict(org_id="org-org",project_id="dev-project",installation_id=installation,kind="runtime-apply",
              idempotency_key="store-test",requested_by="tester",expected_installation_etag=1,
              deadline=datetime.now(timezone.utc)+timedelta(minutes=1))
    with conn.transaction():
        first=store.accept(conn,**args)
    conn.execute("UPDATE bundle_installation SET etag_version=2 WHERE installation_id=%s",(installation,))
    with conn.transaction():
        assert store.accept(conn,**args).replayed
    with pytest.raises(RuntimeConflict):
        with conn.transaction():
            store.accept(conn,**{**args,"requested_by":"different"})
    with pytest.raises(RuntimeRevisionConflict):
        with conn.transaction():
            store.accept(conn,**{**args,"idempotency_key":"new"})
    assert conn.execute("SELECT count(*) FROM extension_runtime_event WHERE operation_id=%s",(first.operation_id,)).fetchone()[0]==1


def test_event_outbox_and_phase_are_atomic(database):
    from datetime import datetime,timezone,timedelta
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
    conn,_,_=database
    installation,_=seed(conn)
    store=RuntimeOperationStore()
    with conn.transaction():
        first=store.accept(conn,org_id="org-org",project_id="dev-project",installation_id=installation,kind="enable",
            idempotency_key="atomic",requested_by="tester",expected_installation_etag=1,
            deadline=datetime.now(timezone.utc)+timedelta(minutes=1))
    with pytest.raises(RuntimeError):
        with conn.transaction():
            store.advance(conn,org_id="org-org",project_id="dev-project",operation_id=first.operation_id,
                          expected_revision=1,phase="validating")
            raise RuntimeError("crash before commit")
    assert conn.execute("SELECT phase FROM extension_runtime_operation WHERE operation_id=%s",(first.operation_id,)).fetchone()[0]=="accepted"
    assert conn.execute("SELECT count(*) FROM extension_runtime_event WHERE operation_id=%s",(first.operation_id,)).fetchone()[0]==1
    assert conn.execute("SELECT count(*) FROM extension_runtime_outbox").fetchone()[0]==1


def test_resource_intent_survives_new_reader_and_replay(database):
    from datetime import datetime,timezone,timedelta
    from aos_api.extension_runtime.reconciler import ResourceJournal
    conn,_,_=database
    _,operation=seed(conn)
    args=dict(org_id="org-org",project_id="dev-project",operation_id=operation,generation=uuid.uuid4(),
              package_id="test-package",package_hash="sha256:"+"a"*64,engine_context="colima-aos-extension",
              expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
    with conn.transaction():
        first=ResourceJournal().prepare(conn,**args)
    with conn.transaction():
        replay=ResourceJournal().prepare(conn,**args)
    assert replay.replayed and replay.resource_id==first.resource_id and replay.identity==first.identity
    recovered=ResourceJournal().unresolved(conn,org_id="org-org",project_id="dev-project")
    assert len(recovered)==1 and recovered[0].identity==first.identity
    assert ResourceJournal().unresolved(conn,org_id="dev-org",project_id="dev-project")==[]
    with conn.transaction():
        assert ResourceJournal().record_cleanup(conn,org_id="org-org",project_id="dev-project",intent=first,removed=False)=="uncertain"
    assert conn.execute("SELECT status FROM extension_runtime_operation").fetchone()[0]=="needs_attention"
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore,RuntimeConflict
    with pytest.raises(RuntimeConflict,match="not confirmed"):
        with conn.transaction():
            RuntimeOperationStore().settle_failed_preparation(conn,org_id="org-org",project_id="dev-project",
                operation_id=operation,expected_revision=2)
    with conn.transaction():
        ResourceJournal().record_cleanup(conn,org_id="org-org",project_id="dev-project",intent=first,removed=False)
    assert conn.execute("SELECT count(*) FROM extension_runtime_event").fetchone()[0]==1
    with pytest.raises(RuntimeError,match="rollback"):
        with conn.transaction():
            ResourceJournal().record_cleanup(conn,org_id="org-org",project_id="dev-project",intent=first,removed=True)
            raise RuntimeError("rollback")
    assert len(ResourceJournal().unresolved(conn,org_id="org-org",project_id="dev-project"))==1
    with conn.transaction():
        assert ResourceJournal().record_cleanup(conn,org_id="org-org",project_id="dev-project",intent=first,removed=True)=="released"
    assert ResourceJournal().unresolved(conn,org_id="org-org",project_id="dev-project")==[]
    assert conn.execute("SELECT status FROM extension_runtime_operation").fetchone()[0]=="needs_attention"
    assert conn.execute("SELECT count(*) FROM extension_runtime_outbox").fetchone()[0]==2
    with conn.transaction():
        settled=RuntimeOperationStore().settle_failed_preparation(conn,org_id="org-org",project_id="dev-project",
            operation_id=operation,expected_revision=3)
        assert settled.status=="failed" and settled.revision==4
    assert conn.execute("SELECT count(*) FROM extension_runtime_outbox").fetchone()[0]==3


@pytest.mark.parametrize("condition",["normal","expired","terminal"])
def test_resource_creation_claim_is_one_shot(database,condition):
    from datetime import datetime,timezone,timedelta
    from aos_api.extension_runtime.reconciler import ResourceJournal
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    conn,_,_=database
    _,operation=seed(conn)
    journal=ResourceJournal()
    with conn.transaction():
        intent=journal.prepare(conn,org_id="org-org",project_id="dev-project",operation_id=operation,
            generation=uuid.uuid4(),package_id="claim-test",package_hash="sha256:"+"b"*64,
            engine_context="colima-aos-extension",expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
    args=dict(org_id="org-org",project_id="dev-project",resource_id=intent.resource_id)
    if condition=="expired":
        conn.execute("UPDATE extension_runtime_resource_lease SET expires_at=now()-interval '1 second'")
    elif condition=="terminal":
        conn.execute("UPDATE extension_runtime_operation SET status='cancelled'")
    if condition=="normal":
        with conn.transaction():
            assert journal.claim_create(conn,**args).identity==intent.identity
    with pytest.raises(RuntimeConflict):
        with conn.transaction():
            ResourceJournal().claim_create(conn,**args)
    # Claimed is not released, nor proof of creation; restart must reconcile it.
    assert len(journal.unresolved(conn,org_id="org-org",project_id="dev-project"))==1


def test_concurrent_claim_and_rollback(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from datetime import datetime,timezone,timedelta
    from aos_api.extension_runtime.reconciler import ResourceJournal
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    conn,_,schema=database
    _,operation=seed(conn)
    with conn.transaction():
        intent=ResourceJournal().prepare(conn,org_id="org-org",project_id="dev-project",operation_id=operation,
            generation=uuid.uuid4(),package_id="parallel-test",package_hash="sha256:"+"c"*64,
            engine_context="colima-aos-extension",expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
    args=dict(org_id="org-org",project_id="dev-project",resource_id=intent.resource_id)
    with pytest.raises(RuntimeError,match="rollback"):
        with conn.transaction():
            ResourceJournal().claim_create(conn,**args)
            raise RuntimeError("rollback")
    barrier=Barrier(2)
    def claim():
        with psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",autocommit=True) as worker:
            worker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            worker.execute("SET statement_timeout='5s'")
            barrier.wait(timeout=5)
            try:
                with worker.transaction():
                    ResourceJournal().claim_create(worker,**args)
                return "claimed"
            except RuntimeConflict:
                return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(claim) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures)==["claimed","rejected"]


def test_fence_epoch_event_and_outbox_are_atomic(database):
    from aos_api.extension_runtime.binding_store import RuntimeBindingStore
    from aos_api.extension_runtime.lifecycle_store import RuntimeRevisionConflict
    conn,_,_=database
    installation,operation=seed(conn)
    conn.execute("UPDATE extension_runtime_operation SET kind='disable'")
    generation=uuid.uuid4()
    conn.execute("""INSERT INTO extension_runtime_binding
        (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
         profile_ref,config_ref,desired_state,observed_state,enabled,operation_fence)
        VALUES('org-org','dev-project',%s,%s,1,'{}','test','{}','enabled','ready',true,false)""",
        (installation,generation))
    args=dict(org_id="org-org",project_id="dev-project",installation_id=installation,generation=generation,
              operation_id=operation,expected_operation_revision=1,expected_binding_revision=1)
    with pytest.raises(RuntimeError,match="rollback"):
        with conn.transaction():
            RuntimeBindingStore().fence(conn,**args)
            raise RuntimeError("rollback")
    assert conn.execute("SELECT enabled,execution_epoch FROM extension_runtime_binding").fetchone()==(True,1)
    assert conn.execute("SELECT count(*) FROM extension_runtime_outbox").fetchone()[0]==0
    with conn.transaction():
        assert RuntimeBindingStore().fence(conn,**args).phase=="fencing"
    assert conn.execute("SELECT enabled,operation_fence,execution_epoch,revision FROM extension_runtime_binding").fetchone()==(False,True,2,2)
    assert conn.execute("SELECT count(*) FROM extension_runtime_outbox").fetchone()[0]==1
    with pytest.raises(RuntimeRevisionConflict):
        with conn.transaction():
            RuntimeBindingStore().fence(conn,**args)
    assert conn.execute("SELECT execution_epoch FROM extension_runtime_binding").fetchone()[0]==2


def test_runtime_role_rejects_privileged_session_even_after_set_role(database):
    from aos_api.extension_runtime.storage_ports import require_runtime_role,StorageRoleDenied
    conn,role,_=database
    args=dict(org_id="org-org",project_id="dev-project",protected_tables=("extension_runtime_binding",))
    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
    with pytest.raises(StorageRoleDenied,match="privileged"):
        with conn.transaction():
            require_runtime_role(conn,**args)
    conn.execute("RESET ROLE")
    conn.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(role)))
    try:
        with pytest.raises(StorageRoleDenied,match="scope"):
            with conn.transaction():
                require_runtime_role(conn,**args)
        with conn.transaction():
            conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
            require_runtime_role(conn,**args)
        with pytest.raises(StorageRoleDenied,match="isolation"):
            with conn.transaction():
                conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
                require_runtime_role(conn,**{**args,"protected_tables":("bundle_installation",)})
    finally:
        conn.execute("RESET SESSION AUTHORIZATION")


def test_runtime_role_rejects_bypass_membership(database):
    from aos_api.extension_runtime.storage_ports import require_runtime_role,StorageRoleDenied
    conn,role,_=database
    elevated="ar1c_bypass_"+uuid.uuid4().hex
    conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN BYPASSRLS").format(sql.Identifier(elevated)))
    try:
        conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(elevated),sql.Identifier(role)))
        conn.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(role)))
        try:
            with pytest.raises(StorageRoleDenied,match="privileged"):
                with conn.transaction():
                    conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
                    require_runtime_role(conn,org_id="org-org",project_id="dev-project",
                        protected_tables=("extension_runtime_binding",))
        finally:
            conn.execute("RESET SESSION AUTHORIZATION")
    finally:
        conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(elevated)))


def test_operation_cas_uses_etag_not_fact_or_active_revision(database):
    from datetime import datetime,timezone,timedelta
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore,RuntimeRevisionConflict
    conn,_,_=database
    installation,_=seed(conn)
    conn.execute("ALTER TABLE bundle_installation ADD COLUMN current_revision bigint DEFAULT 5, ADD COLUMN active_revision bigint DEFAULT 3")
    conn.execute("UPDATE bundle_installation SET etag_version=9")
    args=dict(org_id="org-org",project_id="dev-project",installation_id=installation,
        kind="runtime-apply",requested_by="tester",deadline=datetime.now(timezone.utc)+timedelta(minutes=1))
    for incorrect in (3,5):
        with pytest.raises(RuntimeRevisionConflict):
            with conn.transaction():
                RuntimeOperationStore().accept(conn,**args,idempotency_key=str(incorrect),expected_installation_etag=incorrect)
    with conn.transaction():
        assert RuntimeOperationStore().accept(conn,**args,idempotency_key="correct-etag",expected_installation_etag=9).status=="accepted"


@pytest.mark.parametrize("scope",["org-org","dev-org",None])
def test_store_writes_with_non_owner_role_obey_rls(database,scope):
    from datetime import datetime,timezone,timedelta
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
    conn,role,_=database
    installation,_=seed(conn)
    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
    if scope:
        conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id','dev-project',false)",(scope,))
    args=dict(org_id="org-org",project_id="dev-project",installation_id=installation,kind="runtime-apply",
              idempotency_key="role-write",requested_by="tester",expected_installation_etag=1,
              deadline=datetime.now(timezone.utc)+timedelta(minutes=1))
    if scope=="org-org":
        with conn.transaction():
            assert RuntimeOperationStore().accept(conn,**args).status=="accepted"
    else:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                RuntimeOperationStore().accept(conn,**args)
