"""Fixed recovery receipt requires fresh current authority on every use."""
from datetime import timedelta
import psycopg
import pytest
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.pipeline_snapshot_group_recovery_authority import SnapshotGroupRecoveryAuthority
from aos_api.tenant_scope import TenantScope

pytest_plugins=('test_snapshot_group_recovery_owner_pg',)


@pytest.fixture
def authority_case(recovery_case):
    runtime,owner,command,state=recovery_case
    with runtime._transaction(command['scope']) as conn:
        receipt=owner.renew(conn,**command)
        definition=runtime._definitions.read(conn,scope=command['scope'],definition_id=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-'))
        bindings=runtime._definitions._saved_bindings(conn,command['scope'],definition['body'])
        original=runtime._claims.read(conn,scope=command['scope'],group_id=command['group_id'])
        runs={m['scheduleId']:m['runId'] for m in original['members']}
        pairs=tuple((b.control_ref,runs[b.schedule_id]) for b in bindings)
    authority=SnapshotGroupRecoveryAuthority(definitions=runtime._definitions,claims=runtime._claims,ref=receipt['ref'])
    args=dict(scope=command['scope'],actor=command['actor'],bindings=pairs)
    return runtime,owner,command,state,receipt,authority,args


def test_exact_current_receipt_retains_original_facts_and_new_execution_window(authority_case):
    runtime,owner,command,state,receipt,authority,args=authority_case
    with runtime._transaction(command['scope']) as conn:
        def inspect(current):
            assert current.receipt==receipt
            assert current.facts.manifest_hash==command['input_manifest_hash']
            assert current.execution.group.not_before==command['not_before']
            old={c.ref.resource_id:c for c in current.facts.controls}
            assert all(ref.revision==old[ref.resource_id].ref.revision+1 for ref,_,_ in current.execution.group.members)
            return 'verified'
        assert authority.run_current(conn,**args,execute=inspect)=='verified'
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12
    assert state['calls']==1


def test_wrong_executor_tenant_and_member_pairs_never_enter_consumer(authority_case):
    runtime,_,command,state,_,authority,args=authority_case
    seen=[]
    with runtime._transaction(command['scope']) as conn:
        with pytest.raises(PermissionError,match='executor'):
            authority.run_current(conn,**(args|dict(actor='another-executor')),execute=seen.append)
        with pytest.raises(ValueError,match='complete'):
            authority.run_current(conn,**(args|dict(bindings=args['bindings'][:-1])),execute=seen.append)
        pairs=args['bindings'];wrong=(pairs[0][0],'another-original-run')
        with pytest.raises(ValueError,match='pairs'):
            authority.run_current(conn,**(args|dict(bindings=(wrong,)+pairs[1:])),execute=seen.append)
        with pytest.raises(PermissionError,match='tenant'):
            authority.run_current(conn,**(args|dict(scope=TenantScope('dev-org','dev-project'))),execute=seen.append)
    with runtime._transaction(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(LookupError):
            authority.run_current(conn,**(args|dict(scope=TenantScope('dev-org','dev-project'))),execute=seen.append)
    assert seen==[] and state['calls']==1


def test_disable_before_or_during_consumer_invalidates_receipt(authority_case):
    runtime,_,command,state,receipt,authority,args=authority_case
    definition_id=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-')
    with runtime._transaction(command['scope']) as conn:
        def disable(_current):
            runtime._definitions.transition(conn,scope=command['scope'],definition_id=definition_id,actor=command['actor'],
                intent='disable',expected_ref=receipt['body']['currentDefinitionRef'],idempotency_key='disable-inside')
        with pytest.raises(ValueError,match='current enabled'):
            authority.run_current(conn,**args,execute=disable)
        assert runtime._definitions.read(conn,scope=command['scope'],definition_id=definition_id)['ref']==receipt['body']['currentDefinitionRef']
        disable(None)
    with runtime._transaction(command['scope']) as conn:
        with pytest.raises(ValueError,match='current enabled'):
            authority.run_current(conn,**args,execute=lambda _:pytest.fail('disabled callback entered'))
    assert state['calls']==1


def test_second_renewal_invalidates_fixed_prior_receipt(authority_case):
    runtime,owner,command,state,receipt,authority,args=authority_case
    with runtime._transaction(command['scope']) as conn:
        owner.renew(conn,**(command|dict(expected_definition_ref=receipt['body']['currentDefinitionRef'],
            expected_recovery_ref=receipt['ref'],expires_at=command['expires_at']+timedelta(hours=1),idempotency_key='next-window')))
    with runtime._transaction(command['scope']) as conn:
        with pytest.raises(ValueError,match='receipt is not current'):
            authority.run_current(conn,**args,execute=lambda _:pytest.fail('stale callback entered'))
    assert state['calls']==1


def test_current_persisted_permission_is_rechecked_on_use(authority_case):
    runtime,_,command,state,_,authority,args=authority_case
    with runtime._completion._connect() as connection:dsn=connection.info.dsn
    # Named isolated test database administration; never touch a real tenant.
    with psycopg.connect(dsn) as admin:
        admin.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
            (*command['scope'].key,command['actor']))
    with runtime._transaction(command['scope']) as conn:
        with pytest.raises(RuntimeConflict,match='membership'):
            authority.run_current(conn,**args,execute=lambda _:pytest.fail('revoked callback entered'))
    assert state['calls']==1


def test_async_result_and_mid_consumer_window_expiry_are_rejected(authority_case,monkeypatch):
    runtime,_,command,state,_,authority,args=authority_case
    with runtime._transaction(command['scope']) as conn:
        async def deferred(_):return 'not executed'
        with pytest.raises(ValueError,match='finish within'):
            authority.run_current(conn,**args,execute=deferred)
        import aos_api.pipeline_snapshot_group_owner as group_module
        clock=group_module._now
        def expires(_):monkeypatch.setattr(group_module,'_now',lambda c:clock(c)+timedelta(days=2))
        with pytest.raises(PermissionError,match='window'):
            authority.run_current(conn,**args,execute=expires)
    assert state['calls']==1
