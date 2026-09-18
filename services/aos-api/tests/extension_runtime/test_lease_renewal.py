from datetime import datetime, UTC, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from psycopg.pq import TransactionStatus
from aos_api.extension_runtime.lease_renewal import renew_verified_lease
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


def test_only_positive_health_age_is_retryable_stale():
    from aos_api.extension_runtime.verification_commit import HealthObservationStale,_fresh_health
    now=datetime.now(UTC)
    conn=MagicMock()
    conn.execute.return_value.fetchone.return_value={'now':now}
    with pytest.raises(HealthObservationStale):_fresh_health(conn,now-timedelta(seconds=4))
    with pytest.raises(RuntimeConflict) as future:_fresh_health(conn,now+timedelta(seconds=1))
    assert type(future.value) is RuntimeConflict


def test_health_freshness_is_checked_after_identity_locks_before_slow_revalidation():
    from inspect import getsource
    from aos_api.extension_runtime.verification_commit import commit_verified
    renewal=getsource(renew_verified_lease)
    verification=getsource(commit_verified)
    assert renewal.index("SELECT installation_revision") < renewal.index("_fresh_health(")
    assert renewal.index("_fresh_health(") < renewal.index("revalidator.revalidate_in_transaction")
    assert verification.index("SELECT generation FROM extension_runtime_binding") < verification.index("_fresh_health(")
    assert verification.index("_fresh_health(") < verification.index("revalidator.revalidate_in_transaction")


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
        if 'SELECT 1 FROM extension_runtime_execution_attempt' in query:
            cursor.fetchone.return_value=None
        elif 'SELECT etag_version' in query:
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


@pytest.mark.parametrize('case',['valid','terminal','fenced','epoch','attempt_expired',
    'attempt_ambiguous','proof_drift','resource_expired','binding_drift'])
def test_live_recoverable_store_renews_without_installation_lock(case):
    from aos_api.extension_runtime.lease_renewal import _renew_live_recoverable_store
    now=datetime.now(UTC);installation,operation,generation=uuid4(),uuid4(),uuid4()
    attempt=uuid4();epoch=7
    resources=[(uuid4(),f'container-{i}','sha256:'+str(i)*64) for i in range(1,4)]
    proofs=[{'resourceId':str(r),'containerId':c,'packageHash':p,'claimsHash':'sha256:'+'a'*64}
        for r,c,p in resources]
    queries=[]
    def execute(query,params=None):
        queries.append(query);cursor=MagicMock()
        if 'SELECT 1 FROM extension_runtime_execution_attempt' in query:
            cursor.fetchone.return_value=None if case=='terminal' else {'?column?':1}
        elif 'SELECT execution_epoch' in query:
            cursor.fetchone.return_value=dict(execution_epoch=epoch,enabled=True,
                operation_fence=case=='fenced',desired_state='enabled',observed_state='ready',
                resource_handle_ref={'preparationOperationId':str(operation),'resources':proofs},revision=9)
        elif 'SELECT attempt_id,accepted_at' in query:
            row=dict(attempt_id=attempt,accepted_at=now-timedelta(seconds=60),
                heartbeat_at=now-timedelta(seconds=10),lease_until=(now-timedelta(seconds=1)
                    if case=='attempt_expired' else now+timedelta(seconds=110)))
            cursor.fetchall.return_value=[] if case=='epoch' else [row,row] if case=='attempt_ambiguous' else [row]
        elif 'SELECT clock_timestamp()' in query:
            cursor.fetchone.return_value={'now':now}
        elif 'SELECT kind,status,phase,revision' in query:
            cursor.fetchone.return_value=dict(kind='runtime-apply',status='succeeded',phase='succeeded',revision=12)
        elif 'SELECT resource_id,container_id' in query:
            cursor.fetchall.return_value=[dict(resource_id=r,container_id=c,
                package_hash=('sha256:'+'f'*64 if case=='proof_drift' and i==0 else p),
                cleanup_state='pending',observed_release=False,
                expires_at=(now-timedelta(seconds=1) if case=='resource_expired' and i==0
                    else now+timedelta(seconds=30))) for i,(r,c,p) in enumerate(resources)]
        elif query.strip().startswith('UPDATE extension_runtime_resource_lease'):
            cursor.fetchall.return_value=([{'resource_id':r} for r,_,_ in resources]
                if case!='binding_drift' else [{'resource_id':resources[0][0]}])
        return cursor
    conn=MagicMock();conn.info.transaction_status=TransactionStatus.INTRANS;conn.execute.side_effect=execute
    args=dict(org_id='org-org',project_id='dev-project',installation_id=installation,
        operation_id=operation,generation=generation,health_checked_at=now)
    with patch('aos_api.extension_runtime.lease_renewal.RuntimeOperationStore._event') as event:
        if case=='terminal':
            assert _renew_live_recoverable_store(conn,**args) is None
            event.assert_not_called()
        elif case=='valid':
            assert _renew_live_recoverable_store(conn,**args)==now+timedelta(seconds=180)
            event.assert_called_once()
        else:
            with pytest.raises(RuntimeConflict):_renew_live_recoverable_store(conn,**args)
            event.assert_not_called()
    assert not any('bundle_installation' in query for query in queries)
    binding_query=next((query for query in queries if 'SELECT execution_epoch' in query),None)
    if case!='terminal':
        assert binding_query is not None and 'FOR UPDATE' not in binding_query
    resource_update=next((query for query in queries
        if query.strip().startswith('UPDATE extension_runtime_resource_lease')),None)
    if resource_update is not None:
        assert 'EXISTS (SELECT 1 FROM extension_runtime_binding' in resource_update


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
