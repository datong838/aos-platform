from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import uuid
import os

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from test_lifecycle_pg import database, seed, pytestmark
from aos_api.extension_runtime.reconciler import ResourceJournal
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict

SCOPE=dict(org_id='org-org',project_id='dev-project')


def setup(database, *, claimed=True, known=True, expired=True):
    conn,_,schema=database
    installation,operation=seed(conn)
    generation=uuid.uuid4()
    conn.execute("""INSERT INTO extension_runtime_binding
        (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
         profile_ref,config_ref,desired_state,observed_state,enabled,operation_fence)
        VALUES('org-org','dev-project',%s,%s,1,'{}','test','{}','enabled','ready',true,false)""",(installation,generation))
    with conn.transaction():
        journal=ResourceJournal()
        intent=journal.prepare(conn,**SCOPE,operation_id=operation,generation=generation,
            package_id='recovery',package_hash='sha256:'+'a'*64,engine_context='colima-aos-extension',
            expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
        if claimed:journal.claim_create(conn,**SCOPE,resource_id=intent.resource_id)
        if known:journal.record_created(conn,**SCOPE,intent=intent,container_id='a'*64)
    if expired:conn.execute("UPDATE extension_runtime_resource_lease SET expires_at=clock_timestamp()-interval '1 second'")
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
    conn.execute('GRANT SELECT,UPDATE,INSERT ON ALL TABLES IN SCHEMA '+schema+' TO aos_runtime')
    @contextmanager
    def connect():
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True,row_factory=dict_row) as worker:
            worker.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            worker.execute('SET SESSION AUTHORIZATION aos_runtime')
            yield worker
    return conn,intent,connect


@pytest.mark.parametrize('mode',['known','unknown','absent','confirmed_absent','still_present',
    'confirm_error','error','unclaimed','live','tenant','context','name'])
def test_recovery_commits_fence_before_owned_cleanup(database,mode):
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    conn,intent,connect=setup(database,claimed=mode!='unclaimed',known=mode not in ('unknown','unclaimed'),expired=mode!='live')
    calls=[]
    class Driver:
        context='other-engine' if mode=='context' else intent.engine_context
        def require_isolation(self):pass
        def remove_owned(self,name,owner,*,expected_container_id=None):
            calls.append((name,owner,expected_container_id))
            assert conn.execute('SELECT enabled,operation_fence FROM extension_runtime_binding').fetchone()==(False,True)
            assert conn.execute('SELECT cleanup_state FROM extension_runtime_resource_lease').fetchone()==('uncertain',)
            if mode=='error':raise RuntimeError('engine failure')
            return mode not in ('absent','confirmed_absent','still_present','confirm_error')
        def confirm_absent(self,name,owner,*,expected_container_id):
            calls.append(('confirm',name,owner,expected_container_id))
            if mode=='confirm_error':raise RuntimeError('engine read failed')
            return mode=='confirmed_absent'
    if mode=='name':conn.execute("UPDATE extension_runtime_resource_lease SET resource_name='aos-ext-wrong'")
    target=SCOPE if mode!='tenant' else {**SCOPE,'org_id':'dev-org'}
    recovery=ExpiredResourceRecovery(connect=connect,driver=Driver())
    if mode in ('live','tenant','context','name'):
        with pytest.raises((RuntimeConflict,LookupError)):
            recovery.run_one(**target,resource_id=intent.resource_id)
        assert not calls
        assert conn.execute('SELECT enabled FROM extension_runtime_binding').fetchone()==(True,)
        return
    result=recovery.run_one(**target,resource_id=intent.resource_id)
    assert result==('uncertain' if mode in ('absent','still_present','confirm_error','error') else 'released')
    assert len(calls)==(0 if mode=='unclaimed' else 2 if mode in (
        'absent','confirmed_absent','still_present','confirm_error') else 1)
    if calls:
        assert calls[0]==(intent.identity.name,intent.identity.owner,None if mode=='unknown' else 'a'*64)
    if len(calls)==2:
        assert calls[1]==('confirm',intent.identity.name,intent.identity.owner,'a'*64)
    before=len(calls)
    if result=='released':
        assert ExpiredResourceRecovery(connect=connect,driver=Driver()).run_one(**target,resource_id=intent.resource_id)=='released'
        assert len(calls)==before
    with pytest.raises(RuntimeConflict):
        with conn.transaction():ResourceJournal().claim_create(conn,**SCOPE,resource_id=intent.resource_id)


@pytest.mark.parametrize('limit',[0,101,True,'1'])
def test_expired_scan_rejects_unbounded_limit(database,limit):
    conn,_,_=database
    with pytest.raises(ValueError):
        with conn.transaction():ResourceJournal().expired(conn,**SCOPE,engine_context='colima-aos-extension',limit=limit)


def test_expired_scan_pages_without_repeating_uncertain(database):
    conn,intent,_=setup(database)
    with conn.transaction():
        first=ResourceJournal().expired(conn,**SCOPE,engine_context=intent.engine_context,limit=1)
        assert first==[intent.resource_id]
        assert ResourceJournal().expired(conn,**SCOPE,engine_context=intent.engine_context,limit=1,after=first[-1])==[]
        assert ResourceJournal().expired(conn,org_id='dev-org',project_id='dev-project',engine_context=intent.engine_context)==[]


def test_recovery_session_lock_excludes_concurrent_engine_call(database):
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    conn,intent,connect=setup(database)
    class Driver:
        context=intent.engine_context
        def require_isolation(self):pass
        def remove_owned(self,*args,**kwargs):
            with pytest.raises(RuntimeConflict,match='already recovering'):
                ExpiredResourceRecovery(connect=connect,driver=self).run_one(**SCOPE,resource_id=intent.resource_id)
            return True
    assert ExpiredResourceRecovery(connect=connect,driver=Driver()).run_one(**SCOPE,resource_id=intent.resource_id)=='released'


def test_observation_commit_failure_keeps_uncertain_after_restart(database,monkeypatch):
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    conn,intent,connect=setup(database)
    original=ResourceJournal.record_cleanup
    def fail_observation(self,db,**args):
        result=original(self,db,**args)
        if args['removed']:raise RuntimeError('observation transaction interrupted')
        return result
    monkeypatch.setattr(ResourceJournal,'record_cleanup',fail_observation)
    class Driver:
        context=intent.engine_context
        exists=True
        def require_isolation(self):pass
        def remove_owned(self,*args,**kwargs):
            existed=self.exists;self.exists=False
            return existed
    driver=Driver()
    with pytest.raises(RuntimeError,match='interrupted'):
        ExpiredResourceRecovery(connect=connect,driver=driver).run_one(**SCOPE,resource_id=intent.resource_id)
    assert conn.execute('SELECT cleanup_state,observed_release FROM extension_runtime_resource_lease').fetchone()==('uncertain',False)
    assert conn.execute('SELECT enabled,operation_fence FROM extension_runtime_binding').fetchone()==(False,True)
    monkeypatch.setattr(ResourceJournal,'record_cleanup',original)
    # Even though this test knows deletion happened, the new worker cannot prove it.
    assert ExpiredResourceRecovery(connect=connect,driver=driver).run_one(**SCOPE,resource_id=intent.resource_id)=='uncertain'
    assert conn.execute('SELECT count(*) FROM extension_runtime_event WHERE type=\'resource_released\'').fetchone()==(0,)


def test_recovery_rechecks_lease_after_waiting_on_operation_lock(database):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    conn,intent,connect=setup(database)
    entered=threading.Event()
    pids=[]
    @contextmanager
    def observed_connect():
        with connect() as worker:
            pids.append(worker.info.backend_pid);entered.set()
            yield worker
    class Driver:
        context=intent.engine_context
        def require_isolation(self):raise AssertionError('must not touch engine')
    def recover():return ExpiredResourceRecovery(connect=observed_connect,driver=Driver()).run_one(**SCOPE,resource_id=intent.resource_id)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with conn.transaction():
            conn.execute('SELECT operation_id FROM extension_runtime_operation FOR UPDATE')
            future=pool.submit(recover)
            assert entered.wait(2)
            end=time.monotonic()+.8
            while not conn.execute('SELECT cardinality(pg_blocking_pids(%s))>0',(pids[0],)).fetchone()[0]:
                assert time.monotonic()<end
                time.sleep(.01)
            # Models maintenance/renewal race before recovery obtains the lock.
            conn.execute("UPDATE extension_runtime_resource_lease SET expires_at=clock_timestamp()+interval '1 minute'")
        with pytest.raises(RuntimeConflict,match='live'):future.result(timeout=3)
    assert conn.execute('SELECT enabled FROM extension_runtime_binding').fetchone()==(True,)


@pytest.mark.parametrize('status',[1,2,3,4])
def test_recovery_rejects_non_idle_before_sql(status):
    from types import SimpleNamespace
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    @contextmanager
    def connect():yield SimpleNamespace(info=SimpleNamespace(transaction_status=status))
    with pytest.raises(RuntimeConflict,match='idle'):
        ExpiredResourceRecovery(connect=connect,driver=SimpleNamespace(context='colima-aos-extension')).run_one(**SCOPE,resource_id=uuid.uuid4())


@pytest.mark.skipif(os.getenv('AOS_EXTENSION_OCI_TEST')!='1',reason='dedicated OCI opt-in required')
def test_new_recovery_process_removes_real_oci_from_persisted_identity(database,tmp_path):
    import subprocess
    import sys
    from test_persistent_supervisor import build_session_image
    from aos_api.extension_runtime.oci_driver import OciDriver
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    conn,intent,connect=setup(database,known=False,expired=False)
    image,_=build_session_image(tmp_path)
    driver=OciDriver(context=intent.engine_context)
    driver.require_isolation()
    container=driver.create_session(image,intent.identity.name,intent.identity.owner)
    try:
        with conn.transaction():ResourceJournal().record_created(conn,**SCOPE,intent=intent,container_id=container)
        # Persist another still-live generation: expired cleanup must not touch it.
        original=conn.execute('SELECT installation_id FROM bundle_installation').fetchone()[0]
        other=uuid.uuid4()
        conn.execute("""INSERT INTO extension_runtime_binding
            (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
             profile_ref,config_ref,desired_state,observed_state,enabled,operation_fence)
            VALUES('org-org','dev-project',%s,%s,1,'{}','test','{}','enabled','ready',true,false)""",(original,other))
        conn.execute("UPDATE extension_runtime_resource_lease SET expires_at=clock_timestamp()-interval '1 second'")
        del driver
        # Fresh interpreter receives only isolated schema and durable resource ID,
        # not the original driver/owner/intent/container state from this process.
        program='''
from contextlib import contextmanager
import sys
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
from aos_api.extension_runtime.oci_driver import OciDriver
@contextmanager
def connect():
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True,row_factory=dict_row) as conn:
        conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(sys.argv[1])))
        conn.execute('SET SESSION AUTHORIZATION aos_runtime')
        yield conn
result=ExpiredResourceRecovery(connect=connect,driver=OciDriver(context='colima-aos-extension')).run_one(org_id='org-org',project_id='dev-project',resource_id=sys.argv[2])
assert result=='released'
print('RECOVERY_RELEASED')
'''
        outcome=subprocess.run([sys.executable,'-c',program,database[2],str(intent.resource_id)],capture_output=True,text=True,timeout=45)
        assert outcome.returncode==0, outcome.stderr
        assert 'RECOVERY_RELEASED' in outcome.stdout
        assert conn.execute('SELECT enabled,operation_fence FROM extension_runtime_binding WHERE generation=%s',(other,)).fetchone()==(True,False)
        assert conn.execute('SELECT observed_release FROM extension_runtime_resource_lease').fetchone()==(True,)
        assert OciDriver(context=intent.engine_context).remove_owned(intent.identity.name,intent.identity.owner,expected_container_id=container) is False
        assert ExpiredResourceRecovery(connect=connect,driver=OciDriver(context=intent.engine_context)).run_one(**SCOPE,resource_id=intent.resource_id)=='released'
    finally:
        OciDriver(context=intent.engine_context).remove_owned(intent.identity.name,intent.identity.owner,expected_container_id=container)
