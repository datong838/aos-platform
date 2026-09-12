from datetime import datetime, UTC, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from psycopg.pq import TransactionStatus
from aos_api.extension_runtime.lease_renewal import renew_verified_lease
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


@pytest.mark.parametrize('case', ['valid','configured','denied','binding_lost','conditions','expired','resource_drift'])
def test_renewal_checks_authority_binding_and_live_resources(case):
    conn, store, validator = MagicMock(), MagicMock(), MagicMock()
    conn.info.transaction_status = TransactionStatus.INTRANS
    installation, operation, generation = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    proof = [{'resourceId':str(uuid4())}]
    writes = []
    def execute(query, params=None):
        cursor = MagicMock()
        if 'SELECT etag_version' in query:
            cursor.fetchone.return_value={'etag_version':7}
        elif 'SELECT kind,status,phase' in query:
            cursor.fetchone.return_value=dict(kind='runtime-apply',status='succeeded',phase='succeeded',requested_by='actor',revision=10)
        elif 'SELECT installation_revision' in query:
            cursor.fetchone.return_value=dict(installation_revision=7,package_lock_ref={'lockHash':'lock'},
                observed_state='unknown' if case in ('binding_lost','configured') else 'ready',desired_state='disabled',
                enabled=False,operation_fence=True,revision=9,config_ref={'configurationId':str(installation),'revision':1,'hash':'sha256:'+'a'*64},
                resource_handle_ref={'preparationOperationId':str(operation),'resources':[] if case=='resource_drift' else proof})
        elif 'SELECT o.operation_id' in query:
            from aos_api.extension_runtime.lifecycle_store import _digest
            payload=dict(installationId=str(installation),generation=str(generation),configRef={'configurationId':str(installation),'revision':1,'hash':'sha256:'+'a'*64},bindingRevision=9,executionEpoch=2,enabled=False,observedState='unknown')
            cursor.fetchall.return_value=[dict(operation_id=uuid4(),status='succeeded',phase='succeeded',deadline=now-timedelta(seconds=1),payload=payload,payload_hash=_digest(payload))] if case=='configured' else []
        elif 'SELECT clock_timestamp()' in query:
            cursor.fetchone.return_value={'now':now}
        elif query.strip().startswith('UPDATE'):
            writes.append(query)
            cursor.fetchall.return_value=[] if case=='expired' else [{'resource_id':uuid4()}]
        return cursor
    conn.execute.side_effect=execute
    store.lock_for_transition_in_transaction.return_value.record=SimpleNamespace(state='active',current_revision=7)
    permission=MagicMock(return_value=case!='denied')
    conditions=MagicMock(return_value=case!='conditions')
    with patch('aos_api.extension_runtime.lease_renewal._load_current_lock',return_value=SimpleNamespace(lock_hash='lock')), patch(
        'aos_api.extension_runtime.lease_renewal._expected_backend_claims',return_value={'package':'claims'}), patch(
        'aos_api.extension_runtime.lease_renewal._registered_resources',return_value=(proof,[now+timedelta(seconds=30)])), patch(
        'aos_api.extension_runtime.lease_renewal.RuntimeOperationStore._event') as event:
        args=dict(installation_store=store,revalidator=validator,check_current_permission=permission,
            check_current_conditions=conditions,org_id='org-org',project_id='dev-project',
            installation_id=installation,operation_id=operation,generation=generation,health_checked_at=now)
        if case in ('valid','configured'):
            assert renew_verified_lease(conn,**args)==now+timedelta(seconds=180)
            event.assert_called_once()
        else:
            with pytest.raises(RuntimeConflict):renew_verified_lease(conn,**args)
            event.assert_not_called()
            if case!='expired':assert not writes


@pytest.mark.parametrize('case', ['valid','wrong_generation','wrong_installation','wrong_revision',
    'wrong_config','tampered','missing','ambiguous','enabled','unfenced','uninstalled','stopped'])
def test_configured_fenced_renewal_requires_exact_committed_evidence(case):
    from aos_api.extension_runtime.lease_renewal import _configuration_transition_owned
    from aos_api.extension_runtime.lifecycle_store import _digest
    conn=MagicMock();installation,generation=uuid4(),uuid4()
    config={'configurationId':str(uuid4()),'revision':1,'hash':'sha256:'+'a'*64}
    binding=dict(observed_state='unknown',desired_state='disabled',enabled=False,operation_fence=True,revision=8,config_ref=config)
    payload=dict(installationId=str(installation),generation=str(generation),configRef=config,bindingRevision=8,enabled=False,observedState='unknown')
    if case=='wrong_generation':payload['generation']=str(uuid4())
    if case=='wrong_installation':payload['installationId']=str(uuid4())
    if case=='wrong_revision':payload['bindingRevision']=7
    if case=='wrong_config':payload['configRef']={}
    if case=='enabled':binding['enabled']=True
    if case=='unfenced':binding['operation_fence']=False
    if case=='uninstalled':binding['desired_state']='uninstalled'
    if case=='stopped':binding['observed_state']='stopped'
    row=dict(operation_id=uuid4(),status='succeeded',phase='succeeded',deadline=datetime.now(UTC)-timedelta(days=1),payload=payload,payload_hash='tampered' if case=='tampered' else _digest(payload))
    conn.execute.return_value.fetchall.return_value=[] if case=='missing' else [row,row] if case=='ambiguous' else [row]
    assert _configuration_transition_owned(conn,target=('org-org','dev-project',installation),generation=generation,binding=binding) is (case in ('valid','reconfiguring'))
    assert all(not str(call.args[0]).strip().startswith('UPDATE') for call in conn.execute.call_args_list)


@pytest.mark.parametrize('case', ['valid','reconfiguring','expired','wrong_generation','wrong_revision','wrong_event','wrong_kind_phase'])
def test_draining_renewal_requires_current_configuration_fence(case):
    from aos_api.extension_runtime.lease_renewal import _configuration_transition_owned
    from aos_api.extension_runtime.lifecycle_store import _digest
    conn=MagicMock();installation,generation=uuid4(),uuid4()
    binding=dict(observed_state='draining',desired_state='enabled' if case=='reconfiguring' else 'disabled',enabled=False,operation_fence=True,revision=8,config_ref=None)
    payload={'previousPhase':'validating' if case!='wrong_event' else 'accepted'}
    conn.execute.return_value.fetchall.return_value=[dict(operation_id=uuid4(),status='running',phase='fencing' if case!='wrong_kind_phase' else 'committing',deadline=datetime.now(UTC)+timedelta(seconds=30),payload=payload,payload_hash=_digest(payload))]
    accepted=SimpleNamespace(generation=str(uuid4()) if case=='wrong_generation' else str(generation),bindingRevision=8 if case=='wrong_revision' else 7)
    with patch('aos_api.extension_runtime.lease_renewal._deadline_valid',return_value=case!='expired'), patch('aos_api.extension_runtime.configuration_request.load_configure_target',return_value=accepted):
        assert _configuration_transition_owned(conn,target=('org-org','dev-project',installation),generation=generation,binding=binding) is (case in ('valid','reconfiguring'))
