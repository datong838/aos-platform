from datetime import datetime,timedelta,timezone
import pytest
from test_lifecycle_pg import database,pytestmark
from test_configuration_store_pg import configuration_case
from aos_api.extension_runtime.configuration_store import append_configuration
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore


@pytest.fixture
def accepted_configuration(configuration_case):
    conn,args=configuration_case
    scope={k:args[k] for k in ('org_id','project_id')}
    with conn.transaction():
        ref=append_configuration(conn,**args)
        op=RuntimeOperationStore().accept(conn,**scope,installation_id=args['installation_id'],kind='configure',
            idempotency_key='consumer-configure',requested_by=args['actor'],expected_installation_etag=1,
            deadline=datetime.now(timezone.utc)+timedelta(minutes=2),configuration_target=dict(
                generation=str(args['generation']),bindingRevision=1,configRef=ref))
    return conn,dict(**scope,operation_id=op.operation_id,expected_revision=1,authorize=args['authorize'])


@pytest.mark.parametrize('failure',[None,'cas','etag','phase','deadline','binding','actor','budget','hash','stopped','uninstalled','rollback'])
def test_begin_configuration_uses_current_authority_and_rolls_back(accepted_configuration,failure):
    from aos_api.extension_runtime.configuration_commit import begin_configuration
    conn,args=accepted_configuration
    if failure=='cas':args['expected_revision']=0
    if failure=='etag':conn.execute('UPDATE bundle_installation SET etag_version=2')
    if failure=='phase':conn.execute("UPDATE extension_runtime_operation SET phase='validating'")
    if failure=='deadline':conn.execute("UPDATE extension_runtime_operation SET deadline=clock_timestamp()-interval '1 second'")
    if failure=='binding':conn.execute('UPDATE extension_runtime_binding SET revision=3')
    if failure=='hash':conn.execute("UPDATE extension_runtime_operation SET request_hash=%s",('sha256:'+'b'*64,))
    if failure=='stopped':conn.execute("UPDATE extension_runtime_binding SET observed_state='stopped'")
    if failure=='uninstalled':conn.execute("UPDATE extension_runtime_binding SET desired_state='uninstalled'")
    if failure in ('actor','budget'):
        conn.execute('RESET ROLE')
        conn.execute('DELETE FROM test_configuration_actors' if failure=='actor' else "DELETE FROM test_configuration_refs WHERE purpose='budget'")
        conn.execute('SET ROLE aos_runtime')
    if failure:
        with pytest.raises((ValueError,PermissionError,RuntimeError)):
            with conn.transaction():
                begin_configuration(conn,**args)
                if failure=='rollback':raise RuntimeError('named rollback')
        assert conn.execute('SELECT execution_epoch FROM extension_runtime_binding').fetchone()==(1,)
    else:
        with conn.transaction():result=begin_configuration(conn,**args)
        assert result.phase=='fencing' and result.revision==3
        assert conn.execute('SELECT enabled,operation_fence,observed_state,execution_epoch FROM extension_runtime_binding').fetchone()==(False,True,'draining',2)
