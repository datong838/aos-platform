"""Completed preparation deadlines must not expire a renewed live generation."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from psycopg.pq import TransactionStatus
from aos_api.extension_runtime.enable_commit import commit_enabled
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


@pytest.mark.parametrize('case', ['renewed', 'enable_expired', 'lease_expired', 'active_child', 'predecessor_unproven'])
def test_enable_uses_current_request_and_live_resource_deadlines(case):
    now=datetime.now(UTC);installation,operation,preparation,generation=[uuid4() for _ in range(4)]
    conn=MagicMock();conn.info.transaction_status=TransactionStatus.INTRANS
    config={'configurationId':str(uuid4()),'revision':1,'hash':'sha256:'+'a'*64}
    deadline=now+timedelta(seconds=-1 if case=='enable_expired' else 60)
    lease_expiry=now+timedelta(seconds=-1 if case=='lease_expired' else 90)
    proof=[{'resourceId':str(uuid4())}]
    def execute(query,params=None):
        result=MagicMock()
        if 'SELECT installation_id,expected_installation_etag' in query:
            result.fetchone.return_value=dict(installation_id=installation,expected_installation_etag=5)
        elif 'SELECT kind,phase,status,revision' in query:
            result.fetchone.return_value=dict(kind='enable',phase='accepted',status='accepted',revision=1,requested_by='actor',deadline=deadline)
        elif 'SELECT phase,status' in query:
            result.fetchone.return_value=dict(phase='succeeded',status='succeeded',deadline=now-timedelta(hours=1))
        elif 'SELECT revision,enabled' in query:
            result.fetchone.return_value=dict(revision=8,enabled=False,operation_fence=True,observed_state='unknown',desired_state='disabled',installation_revision=5,package_lock_ref={'lockHash':'lock'},config_ref=config,resource_handle_ref={'preparationOperationId':str(preparation),'resources':proof},execution_epoch=2)
        return result
    conn.execute.side_effect=execute
    store=MagicMock();store.lock_for_transition_in_transaction.return_value.record=SimpleNamespace(state='active',current=SimpleNamespace(revision=5))
    if case=='active_child':store.guard_no_active_replacement_in_transaction.side_effect=RuntimeConflict('active child exists')
    def resources(db,scope,gen,claims,cutoff):
        if min(cutoff,lease_expiry)<=now:raise RuntimeConflict('current resource or request expired')
        return proof,[cutoff,lease_expiry]
    target=SimpleNamespace(generation=str(generation),bindingRevision=8,configRef=SimpleNamespace(model_dump=lambda **kw:config))
    predecessor=SimpleNamespace(installation_id=str(uuid4()),revision=7,lock_hash='lock') if case=='predecessor_unproven' else None
    with patch('aos_api.extension_runtime.enable_commit._load_current_lock',return_value=SimpleNamespace(lock_hash='lock',payload=SimpleNamespace(current_installation_ref=predecessor))), patch('aos_api.extension_runtime.enable_commit.load_enable_target',return_value=target), patch('aos_api.extension_runtime.enable_commit._target',return_value=('org-org','dev-project',installation,generation)), patch('aos_api.extension_runtime.enable_commit.read_configuration'), patch('aos_api.extension_runtime.enable_commit._expected_backend_claims',return_value={}), patch('aos_api.extension_runtime.enable_commit._registered_resources',side_effect=resources), patch('aos_api.extension_runtime.enable_commit._fresh_health'), patch('aos_api.extension_runtime.enable_commit._deadline_valid',side_effect=lambda db,value:value>now), patch('aos_api.extension_runtime.enable_commit.RuntimeOperationStore') as operations:
        operations.return_value.advance.return_value=SimpleNamespace(revision=2)
        args=dict(installation_store=store,revalidator=MagicMock(),check_current_permission=lambda **kw:True,check_current_conditions=lambda **kw:True,authorize=lambda *a,**kw:True,org_id='org-org',project_id='dev-project',operation_id=operation,expected_revision=1,preparation_operation_id=preparation,generation=generation,health_checked_at=now)
        if case=='renewed':
            commit_enabled(conn,**args)
            operations.return_value._event.assert_called_once()
        else:
            with pytest.raises(RuntimeConflict):commit_enabled(conn,**args)
            operations.return_value._event.assert_not_called()
            assert all(not str(call.args[0]).strip().startswith('UPDATE') for call in conn.execute.call_args_list)
