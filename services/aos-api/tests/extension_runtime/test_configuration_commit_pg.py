from datetime import datetime, timedelta, timezone

import pytest

from test_lifecycle_pg import database, pytestmark
from test_configuration_store_pg import configuration_case
from aos_api.extension_runtime.configuration_store import append_configuration
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
from aos_api.extension_runtime.binding_store import RuntimeBindingStore


@pytest.fixture
def prepared_configuration(configuration_case):
    conn,args=configuration_case
    scope={key:args[key] for key in ('org_id','project_id')}
    with conn.transaction():ref=append_configuration(conn,**args)
    operations=RuntimeOperationStore()
    with conn.transaction():
        accepted=operations.accept(conn,**scope,installation_id=args['installation_id'],kind='configure',
            idempotency_key='apply-configuration',requested_by=args['actor'],expected_installation_etag=1,
            deadline=datetime.now(timezone.utc)+timedelta(minutes=1),configuration_target=dict(
                generation=str(args['generation']),bindingRevision=1,configRef=ref))
        validated=operations.advance(conn,**scope,operation_id=accepted.operation_id,expected_revision=1,phase='validating')
        fenced=RuntimeBindingStore().fence(conn,**scope,installation_id=args['installation_id'],generation=args['generation'],
            operation_id=accepted.operation_id,expected_operation_revision=validated.revision,expected_binding_revision=1)
    def drained(db,**context):
        # Explicit trusted test seam: not production async broker evidence.
        assert db is conn and context['fence_epoch']==2
        assert context['generation']==str(args['generation'])
        return True
    return conn,dict(**scope,operation_id=accepted.operation_id,expected_revision=fenced.revision,
                     authorize=args['authorize'],check_drained=drained),ref


def test_commit_configuration_stays_closed(prepared_configuration):
    from aos_api.extension_runtime.configuration_commit import commit_configuration
    conn,args,ref=prepared_configuration
    with conn.transaction():result=commit_configuration(conn,**args)
    assert result.phase=='succeeded'
    assert conn.execute('SELECT config_ref,enabled,operation_fence,observed_state,desired_state,execution_epoch,revision FROM extension_runtime_binding').fetchone()==(
        ref.model_dump(mode='json'),False,True,'unknown','disabled',2,3)
    assert conn.execute("SELECT count(*) FROM extension_runtime_event WHERE type='configuration_committed'").fetchone()==(1,)
    assert conn.execute('SELECT count(*) FROM extension_runtime_outbox').fetchone()==(6,)
    with pytest.raises(ValueError):
        with conn.transaction():commit_configuration(conn,**args)


def test_old_epoch_work_prevents_configuration_commit(prepared_configuration):
    from aos_api.extension_runtime.configuration_commit import commit_configuration
    conn,args,ref=prepared_configuration
    conn.execute('RESET ROLE')
    conn.execute('CREATE TABLE test_configuration_pending_work(generation uuid,epoch bigint,unresolved boolean)')
    conn.execute('INSERT INTO test_configuration_pending_work SELECT generation,execution_epoch-1,true FROM extension_runtime_binding')
    conn.execute('GRANT SELECT ON test_configuration_pending_work TO aos_runtime')
    conn.execute('SET ROLE aos_runtime')
    def drained(db,**context):
        assert context['fence_epoch']==2
        return db.execute('SELECT count(*) FROM test_configuration_pending_work WHERE generation=%s AND unresolved',
                          (context['generation'],)).fetchone()[0]==0
    args['check_drained']=drained
    with pytest.raises(ValueError):
        with conn.transaction():commit_configuration(conn,**args)
    assert conn.execute('SELECT config_ref,enabled FROM extension_runtime_binding').fetchone()==(None,False)


def test_other_tenant_cannot_commit_configuration(prepared_configuration):
    from aos_api.extension_runtime.configuration_commit import commit_configuration
    conn,args,ref=prepared_configuration
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    args['org_id']='dev-org'
    with pytest.raises(LookupError):
        with conn.transaction():commit_configuration(conn,**args)


@pytest.mark.parametrize('failure',['cas','etag','phase','deadline','binding','unfenced','actor','budget','not_drained','async','late','rollback','fence_event','reference_expired'])
def test_commit_configuration_rejects_and_preserves_fence(prepared_configuration,failure):
    from aos_api.extension_runtime.configuration_commit import commit_configuration
    conn,args,ref=prepared_configuration
    if failure=='cas':args['expected_revision']=0
    if failure=='fence_event':
        conn.execute('UPDATE extension_runtime_operation SET revision=4')
        args['expected_revision']=4
    if failure=='etag':conn.execute('UPDATE bundle_installation SET etag_version=2')
    if failure=='phase':conn.execute("UPDATE extension_runtime_operation SET phase='validating'")
    if failure=='deadline':conn.execute("UPDATE extension_runtime_operation SET deadline=clock_timestamp()-interval '1 second'")
    if failure=='binding':conn.execute('UPDATE extension_runtime_binding SET revision=3')
    if failure=='unfenced':conn.execute('UPDATE extension_runtime_binding SET operation_fence=false')
    if failure in ('actor','budget'):
        conn.execute('RESET ROLE')
        if failure=='actor':conn.execute('DELETE FROM test_configuration_actors')
        else:conn.execute("DELETE FROM test_configuration_refs WHERE purpose='budget'")
        conn.execute('SET ROLE aos_runtime')
    if failure=='not_drained':args['check_drained']=lambda *a,**k:False
    if failure=='async':
        async def deferred(*a,**k):return True
        args['check_drained']=deferred
    if failure=='late':
        def late(db,**_):
            db.execute("UPDATE extension_runtime_operation SET deadline=clock_timestamp()-interval '1 second'")
            return True
        args['check_drained']=late
    if failure=='reference_expired':
        conn.execute('RESET ROLE')
        conn.execute("ALTER TABLE test_configuration_refs ADD COLUMN valid_until timestamptz NOT NULL DEFAULT clock_timestamp()+interval '300 milliseconds'")
        conn.execute('SET ROLE aos_runtime')
        original=args['authorize']
        def current(db,**context):
            original(db,**context)
            return db.execute('SELECT bool_and(valid_until>clock_timestamp()) FROM test_configuration_refs').fetchone()[0]
        def wait_expiry(db,**_):
            db.execute("SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM max(valid_until)-clock_timestamp()))+0.02) FROM test_configuration_refs")
            return True
        args.update(authorize=current,check_drained=wait_expiry)
    with pytest.raises((ValueError,PermissionError,RuntimeError)):
        with conn.transaction():
            commit_configuration(conn,**args)
            if failure=='rollback':raise RuntimeError('test rollback')
    assert conn.execute('SELECT config_ref,enabled FROM extension_runtime_binding').fetchone()==(None,False)
    assert conn.execute("SELECT count(*) FROM extension_runtime_event WHERE type='configuration_committed'").fetchone()==(0,)


@pytest.mark.parametrize('phase', ['draining', 'configured', 'wrong_tenant', 'wrong_generation'])
def test_real_configuration_evidence_admits_only_its_fenced_lease(prepared_configuration, phase):
    from uuid import uuid4
    from aos_api.extension_runtime.configuration_commit import commit_configuration
    from aos_api.extension_runtime.lease_renewal import _configuration_transition_owned
    conn,args,_=prepared_configuration
    if phase!='draining':
        with conn.transaction():commit_configuration(conn,**args)
    fields=('installation_id','generation','observed_state','desired_state','enabled','operation_fence','revision','config_ref')
    row=dict(zip(fields,conn.execute('SELECT '+','.join(fields)+' FROM extension_runtime_binding').fetchone()))
    before=conn.execute('SELECT revision,enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()
    target=(args['org_id'],args['project_id'],row['installation_id'])
    if phase=='wrong_tenant':target=('dev-org',args['project_id'],row['installation_id'])
    generation=uuid4() if phase=='wrong_generation' else row['generation']
    with conn.transaction():
        assert _configuration_transition_owned(conn,target=target,generation=generation,binding=row) is (phase in ('draining','configured'))
    assert conn.execute('SELECT revision,enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()==before
