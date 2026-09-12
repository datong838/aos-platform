import uuid
from types import SimpleNamespace
import pytest
from psycopg.types.json import Jsonb

from test_lifecycle_pg import database, pytestmark
from test_resource_recovery_pg import setup, SCOPE
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeOperationStore, _digest
from aos_api.extension_runtime.reconciler import ResourceJournal


def prepared_cleanup(database,case='valid'):
    conn,intent,connect=setup(database)
    op,installation,generation=conn.execute('SELECT operation_id,installation_id,generation FROM extension_runtime_resource_lease JOIN extension_runtime_operation USING(org_id,project_id,operation_id)').fetchone()
    with conn.transaction():
        ResourceJournal().record_cleanup(conn,**SCOPE,intent=intent,removed=False)
        ResourceJournal().record_cleanup(conn,**SCOPE,intent=intent,removed=True)
    resource,container,digest=conn.execute('SELECT resource_id,container_id,package_hash FROM extension_runtime_resource_lease').fetchone()
    proof={'installationId':str(installation),'generation':str(generation),'resources':[
        {'resourceId':str(resource),'containerId':container,'packageHash':digest,'claimsHash':'sha256:'+'b'*64}]}
    revision=conn.execute('SELECT revision FROM extension_runtime_operation').fetchone()[0]+1
    conn.execute("UPDATE extension_runtime_operation SET phase='succeeded',revision=%s",(revision,))
    if case=='bad-hash':
        conn.execute('INSERT INTO extension_runtime_event(org_id,project_id,operation_id,sequence,event_id,type,payload,payload_hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                     (*SCOPE.values(),op,revision,uuid.uuid4(),'preparation_committed',Jsonb(proof),'sha256:'+'c'*64))
    elif case!='missing-proof':
        with conn.transaction():RuntimeOperationStore._event(conn,*SCOPE.values(),op,revision,'preparation_committed',proof)
    return conn,connect,op,revision,proof


@pytest.mark.parametrize('case',['valid','unreleased','pending','generation','enabled','unfenced','missing-proof','bad-hash','missing-resource','cas','tenant','kind','rollback'])
def test_committed_cleanup_requires_exact_released_fenced_generation(database,case):
    from aos_api.extension_runtime.committed_cleanup import settle_committed_cleanup
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    conn,connect,op,revision,proof=prepared_cleanup(database,case)
    if case=='unreleased':conn.execute('UPDATE extension_runtime_resource_lease SET observed_release=false')
    if case=='pending':conn.execute("UPDATE extension_runtime_resource_lease SET cleanup_state='pending'")
    if case=='generation':conn.execute('UPDATE extension_runtime_binding SET generation=%s',(uuid.uuid4(),))
    if case=='enabled':conn.execute("UPDATE extension_runtime_binding SET enabled=true,operation_fence=false,observed_state='ready'")
    if case=='unfenced':conn.execute('UPDATE extension_runtime_binding SET operation_fence=false')
    if case=='kind':conn.execute("UPDATE extension_runtime_operation SET kind='enable'")
    if case=='missing-resource':conn.execute('DELETE FROM extension_runtime_resource_lease')
    before=conn.execute('SELECT status,revision FROM extension_runtime_operation').fetchone()
    worker=ExpiredResourceRecovery(connect=connect,driver=SimpleNamespace(context='colima-aos-extension'))
    scope={**SCOPE,'org_id':'dev-org'} if case=='tenant' else SCOPE
    def run(expected=revision):
        with worker._idle() as db:
            with worker._transaction(db,scope):
                result=settle_committed_cleanup(db,**scope,operation_id=op,expected_revision=expected)
                if case=='rollback':raise RuntimeError('rollback')
                return result
    if case=='valid':
        result=run()
        assert result.status=='failed' and result.phase=='succeeded'
        assert run(result.revision).replayed
        assert conn.execute("SELECT count(*) FROM extension_runtime_event WHERE type='committed_preparation_released'").fetchone()==(1,)
        assert conn.execute("SELECT payload FROM extension_runtime_event WHERE type='preparation_committed'").fetchone()[0]==proof
    else:
        with pytest.raises((RuntimeConflict,LookupError,RuntimeError)):
            run(revision+1 if case=='cas' else revision)
        assert conn.execute('SELECT status,revision FROM extension_runtime_operation').fetchone()==before


def test_host_recovery_batch_settles_committed_cleanup_without_engine_call(database):
    from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
    conn,connect,op,_,_=prepared_cleanup(database)
    worker=ExpiredResourceRecovery(connect=connect,driver=SimpleNamespace(context='colima-aos-extension'))
    assert worker.run_batch(**SCOPE).settled_operations==(op,)
    assert worker.run_batch(**SCOPE).settled_operations==()
    assert conn.execute('SELECT enabled,operation_fence FROM extension_runtime_binding').fetchone()==(False,True)


def test_cleanup_rejects_privileged_identity(database):
    from aos_api.extension_runtime.committed_cleanup import settle_committed_cleanup
    from aos_api.extension_runtime.storage_ports import StorageRoleDenied
    conn,_,op,revision,_=prepared_cleanup(database)
    with pytest.raises(StorageRoleDenied):
        with conn.transaction():
            settle_committed_cleanup(conn,**SCOPE,operation_id=op,expected_revision=revision)
    assert conn.execute('SELECT status,revision FROM extension_runtime_operation').fetchone()==('needs_attention',revision)
