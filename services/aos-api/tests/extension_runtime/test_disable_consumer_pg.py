from contextlib import contextmanager
from types import SimpleNamespace
import uuid
import pytest

from test_resource_recovery_pg import setup,SCOPE
from test_lifecycle_pg import database,pytestmark
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore,RuntimeConflict


@pytest.mark.parametrize('status',[1,2,3,4])
def test_consumer_rejects_non_idle(status):
    from aos_api.extension_runtime.disable_consumer import RuntimeDisableConsumer
    @contextmanager
    def connect():yield SimpleNamespace(info=SimpleNamespace(transaction_status=status))
    with pytest.raises(RuntimeConflict,match='idle'):
        RuntimeDisableConsumer(connect=connect,installation_store=None,check_current_permission=lambda **k:True,
            check_drained=lambda *a,**k:True).run_once(**SCOPE)


@pytest.mark.parametrize('state',['succeeded','failed','cancelled','accepted','other_kind','committing'])
def test_consumer_reads_current_state_instead_of_replaying_old_event(database,monkeypatch,state):
    from aos_api.extension_runtime.disable_consumer import RuntimeDisableConsumer
    from aos_api.extension_runtime.disable_executor import RuntimeDisableExecutor
    conn,_,connect=setup(database)
    operation,revision=conn.execute('SELECT operation_id,revision FROM extension_runtime_operation').fetchone()
    conn.execute('UPDATE extension_runtime_operation SET kind=%s,status=%s,phase=%s',
        ('runtime-apply' if state=='other_kind' else 'disable','accepted' if state=='other_kind' else 'running' if state=='committing' else state,
         'accepted' if state in ('other_kind','accepted') else state))
    with conn.transaction():RuntimeOperationStore._event(conn,'org-org','dev-project',operation,revision+1,'accepted',{'kind':'disable'})
    conn.execute('UPDATE extension_runtime_operation SET revision=revision+1')
    calls=[]
    def fail(*a,**k):calls.append(k);raise RuntimeConflict('deliberate execution failure')
    monkeypatch.setattr(RuntimeDisableExecutor,'execute',fail)
    consumer=RuntimeDisableConsumer(connect=connect,installation_store=None,check_current_permission=lambda **k:True,
        check_drained=lambda *a,**k:True)
    if state=='accepted':
        with pytest.raises(RuntimeConflict,match='deliberate'):consumer.run_once(**SCOPE)
        assert len(calls)==1
        assert conn.execute('SELECT count(*) FROM extension_runtime_outbox WHERE delivered_at IS NOT NULL').fetchone()==(0,)
    elif state=='other_kind':
        assert consumer.run_once(**SCOPE) is None
        assert not calls
    elif state=='committing':
        result=consumer.run_once(**SCOPE)
        assert result.delivery_status=='deferred' and not calls
        assert conn.execute('SELECT count(*) FROM extension_runtime_outbox WHERE delivered_at IS NOT NULL').fetchone()==(0,)
        assert conn.execute('SELECT count(*) FROM extension_runtime_outbox WHERE claim_until IS NULL AND next_attempt>clock_timestamp()').fetchone()==(1,)
    else:
        result=consumer.run_once(**SCOPE)
        assert result.operation_status==state and result.delivery_status=='acknowledged'
        assert not calls
