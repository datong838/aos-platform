from datetime import datetime, UTC, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from psycopg.pq import TransactionStatus
from aos_api.extension_runtime.lease_renewal import renew_verified_lease
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


@pytest.mark.parametrize('case', ['valid','denied','binding_lost','conditions','expired','resource_drift'])
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
                observed_state='unknown' if case=='binding_lost' else 'ready',desired_state='disabled',
                resource_handle_ref={'preparationOperationId':str(operation),'resources':[] if case=='resource_drift' else proof})
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
        if case=='valid':
            assert renew_verified_lease(conn,**args)==now+timedelta(seconds=180)
            event.assert_called_once()
        else:
            with pytest.raises(RuntimeConflict):renew_verified_lease(conn,**args)
            event.assert_not_called()
            if case!='expired':assert not writes
