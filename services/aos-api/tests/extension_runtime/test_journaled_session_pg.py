import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import uuid
import os
import threading
import psycopg
from psycopg import sql
import pytest
from test_lifecycle_pg import database, seed, pytestmark
from aos_api.extension_runtime.reconciler import ResourceJournal
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


def setup_intent(database):
    conn,role,schema=database
    _,operation=seed(conn)
    with conn.transaction():
        intent=ResourceJournal().prepare(conn,org_id="org-org",project_id="dev-project",operation_id=operation,
            generation=uuid.uuid4(),package_id="example",package_hash="sha256:"+"a"*64,
            engine_context="colima-aos-extension",expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
    def connect():
        result=psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",autocommit=True)
        result.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        result.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        result.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
        return result
    return conn,operation,intent,connect


@pytest.mark.parametrize("unknown",[False,True])
def test_claim_commits_before_engine_and_cleanup_is_immediate(database,monkeypatch,unknown):
    from aos_api.extension_runtime import journaled_session as module
    from aos_api.extension_runtime.oci_driver import CleanupUncertainError
    conn,operation,intent,connect=setup_intent(database)
    calls=[]
    class Driver:
        context="colima-aos-extension"
        def create_session(self,*args):
            assert conn.execute("SELECT create_claimed_at IS NOT NULL FROM extension_runtime_resource_lease").fetchone()[0]
            calls.append("create")
            if unknown:raise CleanupUncertainError(self.context,intent.identity.name,intent.identity.owner)
            return "a"*64
        def remove_owned(self,*args):
            calls.append("remove")
            return not unknown
    @asynccontextmanager
    async def simulated(driver,**kwargs):
        try:
            await asyncio.to_thread(driver.create_session,"image",intent.identity.name,intent.identity.owner)
            # Model immediate supervisor cleanup before the caller leaves context.
            await asyncio.to_thread(driver.remove_owned,intent.identity.name,intent.identity.owner)
            yield "session"
        finally:
            if unknown:await asyncio.to_thread(driver.remove_owned,intent.identity.name,intent.identity.owner)
    monkeypatch.setattr(module,"open_session",simulated)
    async def run():
        async with module.open_journaled_session(Driver(),connect=connect,org_id="org-org",project_id="dev-project",
            resource_id=intent.resource_id,image_id="image",declared={}) as session:
            assert session=="session"
            assert conn.execute("SELECT cleanup_state FROM extension_runtime_resource_lease").fetchone()[0]=="released"
    if unknown:
        with pytest.raises(CleanupUncertainError):asyncio.run(run())
        assert conn.execute("SELECT status FROM extension_runtime_operation WHERE operation_id=%s",(operation,)).fetchone()[0]=="needs_attention"
    else:asyncio.run(run())
    assert conn.execute("SELECT cleanup_state FROM extension_runtime_resource_lease").fetchone()[0]==("uncertain" if unknown else "released")
    before=list(calls)
    with pytest.raises(RuntimeConflict):asyncio.run(run())
    assert calls==before


def test_signed_session_claims_matching_package(database,monkeypatch):
    from test_admission import fixture
    from aos_api.extension_runtime.signed_session import open_signed_session
    from aos_api.extension_runtime import journaled_session
    args,_=fixture()
    conn,_,intent,connect=setup_intent(database)
    conn.execute("UPDATE extension_runtime_resource_lease SET package_id=%s,package_hash=%s",
        (args["selected"].id,args["selected"].content_hash))
    args["driver"].context="colima-aos-extension"
    @asynccontextmanager
    async def simulated(driver,**kwargs):
        assert conn.execute("SELECT create_claimed_at IS NOT NULL FROM extension_runtime_resource_lease").fetchone()[0]
        assert kwargs["image_id"]=="sha256:"+"b"*64
        driver.observe(True)
        yield "signed"
    monkeypatch.setattr(journaled_session,"open_session",simulated)
    async def run():
        async with open_signed_session(**args,connect=connect,org_id="org-org",project_id="dev-project",resource_id=intent.resource_id) as session:
            assert session=="signed"
    asyncio.run(run())
    assert conn.execute("SELECT cleanup_state FROM extension_runtime_resource_lease").fetchone()[0]=="released"


def test_package_mismatch_rolls_back_claim_without_engine(database):
    from aos_api.extension_runtime.journaled_session import open_journaled_session
    conn,_,intent,connect=setup_intent(database)
    class Driver:context="colima-aos-extension"
    async def run():
        async with open_journaled_session(Driver(),connect=connect,org_id="org-org",project_id="dev-project",
            resource_id=intent.resource_id,image_id="image",declared={},
            expected_package=("other","sha256:"+"b"*64)):
            raise AssertionError("must reject")
    with pytest.raises(RuntimeConflict,match="package"):
        asyncio.run(run())
    assert conn.execute("SELECT create_claimed_at FROM extension_runtime_resource_lease").fetchone()[0] is None


def test_context_mismatch_rolls_back_claim_without_engine(database):
    from aos_api.extension_runtime.journaled_session import open_journaled_session
    conn,_,intent,connect=setup_intent(database)
    class Driver:context="wrong-context"
    async def run():
        async with open_journaled_session(Driver(),connect=connect,org_id="org-org",project_id="dev-project",
            resource_id=intent.resource_id,image_id="image",declared={}):
            raise AssertionError("must reject")
    with pytest.raises(RuntimeConflict):asyncio.run(run())
    assert conn.execute("SELECT create_claimed_at FROM extension_runtime_resource_lease").fetchone()[0] is None


def test_cancel_in_claim_window_never_starts_engine(database,monkeypatch):
    from aos_api.extension_runtime import journaled_session as module
    conn,_,intent,connect=setup_intent(database)
    started=threading.Event();finish=threading.Event()
    original=ResourceJournal.claim_create
    def slow_claim(self,*args,**kwargs):
        result=original(self,*args,**kwargs)
        started.set()
        assert finish.wait(5)
        return result
    monkeypatch.setattr(ResourceJournal,"claim_create",slow_claim)
    class Driver:context="colima-aos-extension"
    async def enter():
        async with module.open_journaled_session(Driver(),connect=connect,org_id="org-org",project_id="dev-project",
            resource_id=intent.resource_id,image_id="image",declared={}):
            raise AssertionError("must not start after cancellation")
    async def run():
        task=asyncio.create_task(enter())
        assert await asyncio.to_thread(started.wait,3)
        task.cancel()
        finish.set()
        with pytest.raises(asyncio.CancelledError):await task
    asyncio.run(run())
    assert conn.execute("SELECT create_claimed_at IS NOT NULL,cleanup_state FROM extension_runtime_resource_lease").fetchone()==(True,"uncertain")


@pytest.mark.skipif(os.getenv("AOS_EXTENSION_OCI_TEST")!="1",reason="dedicated OCI opt-in required")
@pytest.mark.parametrize("fail_record",[False,True])
def test_real_container_and_pg_cleanup_before_context_exit(database,tmp_path,monkeypatch,fail_record):
    from test_persistent_supervisor import build_session_image,CONTEXT
    from aos_api.extension_runtime.journaled_session import open_journaled_session
    from aos_api.extension_runtime.oci_driver import OciDriver,CleanupUncertainError
    conn,_,intent,connect=setup_intent(database)
    digest,claims=build_session_image(tmp_path)
    if fail_record:
        def unavailable(*args,**kwargs):raise RuntimeError("simulated journal outage")
        monkeypatch.setattr(ResourceJournal,"record_cleanup",unavailable)
    async def run():
        async with open_journaled_session(OciDriver(context=CONTEXT),connect=connect,org_id="org-org",project_id="dev-project",
            resource_id=intent.resource_id,image_id=digest,declared=claims) as session:
            assert await session.invoke("example_read",{"value":"账本联合验证"})=={"value":"账本联合验证"}
            if fail_record:
                with pytest.raises(CleanupUncertainError) as captured:
                    await session.invoke("example_read",{"bad":True})
                assert captured.value.cleanup_reference=={"context":CONTEXT,"name":intent.identity.name,"owner":intent.identity.owner}
                with connect() as fresh:
                    assert fresh.execute("SELECT cleanup_state,observed_release FROM extension_runtime_resource_lease WHERE resource_id=%s",(intent.resource_id,)).fetchone()==("pending",False)
                return
            with pytest.raises(Exception):await session.invoke("example_read",{"bad":True})
            assert conn.execute("SELECT cleanup_state,observed_release FROM extension_runtime_resource_lease").fetchone()==("released",True)
            assert conn.execute("SELECT count(*) FROM extension_runtime_event WHERE type='resource_released'").fetchone()[0]==1
    if fail_record:
        # Context exit retains the same unresolved cleanup, not silent success.
        with pytest.raises(CleanupUncertainError):asyncio.run(run())
    else:asyncio.run(run())
