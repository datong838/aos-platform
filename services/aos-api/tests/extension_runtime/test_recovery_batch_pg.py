import uuid
from datetime import datetime, timedelta, timezone
import pytest

from test_lifecycle_pg import database, pytestmark
from test_resource_recovery_pg import setup, SCOPE
from aos_api.extension_runtime.reconciler import ResourceJournal
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore, RuntimeConflict


@pytest.mark.parametrize('phase',['accepted','validating','preparing','registered','committing','succeeded'])
@pytest.mark.parametrize('state',['released','uncertain'])
def test_failed_preparation_settlement_preserves_committed_history(database,phase,state):
    conn,intent,_=setup(database)
    with conn.transaction():
        ResourceJournal().record_cleanup(conn,**SCOPE,intent=intent,removed=False)
        ResourceJournal().record_cleanup(conn,**SCOPE,intent=intent,removed=True)
    conn.execute('UPDATE extension_runtime_operation SET phase=%s',(phase,))
    if state=='uncertain':
        # Negative authority fixture: both facts must agree, not just the flag.
        conn.execute("UPDATE extension_runtime_resource_lease SET cleanup_state='uncertain'")
    operation,revision=conn.execute('SELECT operation_id,revision FROM extension_runtime_operation').fetchone()
    args=dict(**SCOPE,operation_id=operation,expected_revision=revision)
    if phase in ('committing','succeeded') or state!='released':
        with pytest.raises(RuntimeConflict):
            with conn.transaction():RuntimeOperationStore().settle_failed_preparation(conn,**args)
        assert conn.execute('SELECT phase,status FROM extension_runtime_operation').fetchone()==(phase,'needs_attention')
    else:
        with conn.transaction():assert RuntimeOperationStore().settle_failed_preparation(conn,**args).status=='failed'


def test_bounded_batch_advances_past_uncertain_and_settles_only_all_released(database):
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    conn,first,connect=setup(database)
    operation,generation=conn.execute('SELECT operation_id,generation FROM extension_runtime_resource_lease').fetchone()
    with conn.transaction():
        other=ResourceJournal().prepare(conn,**SCOPE,operation_id=operation,generation=generation,
            package_id='second',package_hash='sha256:'+'b'*64,engine_context=first.engine_context,
            expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
        ResourceJournal().claim_create(conn,**SCOPE,resource_id=other.resource_id)
    conn.execute("UPDATE extension_runtime_resource_lease SET expires_at=clock_timestamp()-interval '1 second'")
    first_id=min(first.resource_id,other.resource_id)
    owner=conn.execute('SELECT owner_token_ref FROM extension_runtime_resource_lease WHERE resource_id=%s',(first_id,)).fetchone()[0]
    calls=[]
    class Driver:
        context=first.engine_context
        def require_isolation(self):pass
        def remove_owned(self,name,actual_owner,**kwargs):
            calls.append(actual_owner)
            return actual_owner!=owner
    worker=ExpiredResourceRecovery(connect=connect,driver=Driver())
    page=worker.run_batch(**SCOPE,limit=1)
    assert page.results==((first_id,'uncertain'),) and page.cursor==first_id
    revision=conn.execute('SELECT revision FROM extension_runtime_operation').fetchone()[0]
    with pytest.raises(RuntimeConflict):worker.settle_preparation(**SCOPE,operation_id=operation,expected_revision=revision)
    second=worker.run_batch(**SCOPE,limit=1,after=page.cursor)
    assert second.results[0][1]=='released' and second.cursor!=first_id
    assert worker.run_batch(**SCOPE,limit=1,after=second.cursor).results==()
    assert len(calls)==2
    # Actual later deletion observation, then a fresh exact-CAS settlement.
    with conn.transaction():
        intent=first if first.resource_id==first_id else other
        ResourceJournal().record_cleanup(conn,**SCOPE,intent=intent,removed=True)
    revision=conn.execute('SELECT revision FROM extension_runtime_operation').fetchone()[0]
    assert worker.settle_preparation(**SCOPE,operation_id=operation,expected_revision=revision).status=='failed'
    with pytest.raises(RuntimeConflict):worker.settle_preparation(**SCOPE,operation_id=operation,expected_revision=revision)


@pytest.mark.parametrize('limit',[0,101,True])
def test_batch_rejects_invalid_bound_before_effect(database,limit):
    from types import SimpleNamespace
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    _,_,connect=setup(database)
    with pytest.raises(ValueError):ExpiredResourceRecovery(connect=connect,driver=SimpleNamespace(context='colima-aos-extension')).run_batch(**SCOPE,limit=limit)


@pytest.mark.parametrize('reason',['busy','live','permission','database','identity'])
def test_batch_only_skips_known_routing_races(database,monkeypatch,reason):
    from types import SimpleNamespace
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery,ResourceRecoveryBusy
    from aos_api.extension_runtime.reconciler import ResourceStillLive
    conn,intent,connect=setup(database)
    failures={'busy':ResourceRecoveryBusy,'live':ResourceStillLive,'permission':PermissionError,
        'database':RuntimeError,'identity':RuntimeConflict}
    worker=ExpiredResourceRecovery(connect=connect,driver=SimpleNamespace(context=intent.engine_context))
    calls=[]
    def fail(**args):calls.append(args['resource_id']);raise failures[reason]('test failure')
    monkeypatch.setattr(worker,'run_one',fail)
    if reason in ('busy','live'):
        page=worker.run_batch(**SCOPE,limit=1)
        assert page.results==((intent.resource_id,reason),) and page.cursor==intent.resource_id
    else:
        with pytest.raises(failures[reason]):worker.run_batch(**SCOPE,limit=1)
    assert calls==[intent.resource_id]
    assert conn.execute('SELECT enabled FROM extension_runtime_binding').fetchone()==(True,)
