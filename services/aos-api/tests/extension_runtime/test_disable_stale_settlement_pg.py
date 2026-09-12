"""Stale disable fails without moving the current generation or accepted target."""
from types import SimpleNamespace
import pytest
from test_lifecycle_pg import database,pytestmark
from test_disable_target_pg import disable_case
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore


@pytest.mark.parametrize('case',['stale','same','permission','operation_cas','installation_cas','tenant','corrupt_hash','rollback','backwards'])
def test_stale_target_terminal_failure_is_scoped_and_effect_free(database,case):
    from aos_api.extension_runtime.disable_commit import settle_stale_disable_target
    conn,_,_=database;accepted_args=disable_case(conn)
    if case=='backwards':
        conn.execute('UPDATE extension_runtime_binding SET revision=3')
        accepted_args['binding_target']['bindingRevision']=3
    with conn.transaction():accepted=RuntimeOperationStore().accept(conn,**accepted_args)
    conn.execute('UPDATE extension_runtime_binding SET revision=%s',(1 if case=='same' else 2,))
    if case=='backwards':
        # A regressed expected target is not treated as ordinary stale input.
        conn.execute('UPDATE extension_runtime_binding SET revision=1')
    if case=='corrupt_hash':conn.execute("UPDATE extension_runtime_operation SET request_hash=%s WHERE operation_id=%s",('sha256:'+'0'*64,accepted.operation_id))
    before=conn.execute('SELECT revision,enabled,operation_fence,execution_epoch,observed_state FROM extension_runtime_binding').fetchone()
    class Store:
        def lock_for_transition_in_transaction(self,c,**kw):
            row=c.execute('SELECT etag_version FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE',
                (kw['org_id'],kw['project_id'],kw['installation_id'])).fetchone()
            if not row or row[0]!=kw['expected_etag_version']:raise ValueError('installation CAS')
            return SimpleNamespace()
    if case=='installation_cas':conn.execute('UPDATE bundle_installation SET etag_version=2')
    args=dict(org_id='dev-org' if case=='tenant' else 'org-org',project_id='dev-project',
        operation_id=accepted.operation_id,expected_revision=2 if case=='operation_cas' else 1,
        installation_store=Store(),check_current_permission=lambda **kw:case!='permission')
    def execute():
        with conn.transaction():
            result=settle_stale_disable_target(conn,**args)
            if case=='rollback':raise ValueError('rollback')
            return result
    if case in ('stale','same'):
        result=execute()
        if case=='same':assert result is None
        else:
            assert result.status=='failed'
            row=conn.execute('SELECT type,payload FROM extension_runtime_event WHERE operation_id=%s AND sequence=2',(accepted.operation_id,)).fetchone()
            assert row[0]=='disable_target_stale'
            assert row[1]['acceptedBindingRevision']==1 and row[1]['currentBindingRevision']==2
    else:
        with pytest.raises((ValueError,LookupError,PermissionError)):execute()
    assert conn.execute('SELECT revision,enabled,operation_fence,execution_epoch,observed_state FROM extension_runtime_binding').fetchone()==before
    assert conn.execute('SELECT expected_binding_revision FROM extension_runtime_operation WHERE operation_id=%s',(accepted.operation_id,)).fetchone()==(3 if case=='backwards' else 1,)
    state=conn.execute('SELECT status,revision FROM extension_runtime_operation WHERE operation_id=%s',(accepted.operation_id,)).fetchone()
    assert state==('failed',2) if case=='stale' else state==('accepted',1)


def test_executor_commits_stale_failure_without_entering_drain(database,monkeypatch):
    from contextlib import contextmanager
    from aos_api.extension_runtime.disable_executor import RuntimeDisableExecutor
    conn,_,_=database;args=disable_case(conn)
    with conn.transaction():accepted=RuntimeOperationStore().accept(conn,**args)
    conn.execute('UPDATE extension_runtime_binding SET revision=2')
    store=SimpleNamespace(lock_for_transition_in_transaction=lambda *a,**kw:SimpleNamespace())
    def forbidden(*a,**kw):raise AssertionError('stale request must not enter drain')
    worker=RuntimeDisableExecutor(connect=forbidden,installation_store=store,
        check_current_permission=lambda **kw:True,check_drained=forbidden)
    calls=[]
    @contextmanager
    def scoped(scope):
        calls.append(scope)
        with conn.transaction():yield conn
    monkeypatch.setattr(worker,'_connection',scoped)
    result=worker.execute(org_id='org-org',project_id='dev-project',operation_id=accepted.operation_id,expected_revision=1)
    assert result.status=='failed' and len(calls)==1
    assert conn.execute('SELECT status FROM extension_runtime_operation WHERE operation_id=%s',(accepted.operation_id,)).fetchone()==('failed',)
