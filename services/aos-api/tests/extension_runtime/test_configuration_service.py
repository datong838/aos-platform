from datetime import datetime,timezone
from unittest.mock import MagicMock,patch
from uuid import uuid4

import pytest


@pytest.mark.parametrize('kind',['configure','enable'])
@pytest.mark.parametrize('failure',[None,'permission','state','busy','pure_content'])
def test_configuration_command_is_acceptance_only(kind,failure):
    from aos_api.extension_runtime.configuration_service import RuntimeConfigurationService
    store=MagicMock();reader=MagicMock();validator=MagicMock();authorize=MagicMock();conn=MagicMock()
    target=dict(generation=str(uuid4()),bindingRevision=2,configRef=dict(configurationId=str(uuid4()),revision=1,hash='sha256:'+'a'*64))
    store.lock_for_transition_in_transaction.return_value.record.state='draft' if failure=='state' else 'active'
    validator.revalidate_in_transaction.return_value.checked_at=datetime.now(timezone.utc)
    validator.revalidate_in_transaction.return_value.runtime_members=() if failure=='pure_content' else ('test-runtime',)
    def execute(query,params=None):
        row=MagicMock()
        if 'status NOT IN' in query:row.fetchone.return_value={'operation_id':uuid4()} if failure=='busy' else None
        elif 'SELECT config_ref' in query:row.fetchone.return_value={'config_ref':target['configRef']}
        else:row.fetchone.return_value={'installation_id':uuid4()}
        return row
    conn.execute.side_effect=execute
    def command(**kw):
        assert kw['current_check'](conn) is True
        return kw['handler'](conn)
    store.execute_idempotent.side_effect=command
    service=RuntimeConfigurationService(installation_store=store,installation_reader=reader,revalidator=validator,authorize=authorize)
    with patch('aos_api.extension_runtime.configuration_service.read_configuration') as read,patch(
        'aos_api.extension_runtime.configuration_service._load_current_lock'),patch(
        'aos_api.extension_runtime.configuration_service._require_lock_markings'),patch(
        'aos_api.extension_runtime.configuration_service.RuntimeOperationStore') as operations:
        operations.return_value.accept.return_value=MagicMock(operation_id=uuid4(),phase='accepted',status='accepted',revision=1)
        if failure=='permission':read.side_effect=PermissionError('revoked')
        args=dict(installation_id=str(uuid4()),kind=kind,org_id='org-org',project_id='dev-project',actor='installer',
            roles=['asset-installer'],markings=[],idempotency_key='request',if_match='"4"',target=target)
        if failure:
            with pytest.raises((ValueError,PermissionError)):service.request(**args)
            operations.return_value.accept.assert_not_called()
        else:
            result=service.request(**args)
            assert result.status_code==202
            assert operations.return_value.accept.call_args.kwargs['configuration_target']==target
            assert store.execute_idempotent.call_args.kwargs['operation']=='runtime_installations.'+kind
    store.append_verify_in_transaction.assert_not_called()
