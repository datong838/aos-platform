"""Actual scoped commands; named isolated drain fixture is not a business broker."""
import pytest
from contextlib import contextmanager


def exercise_disable(worker, reader, scope, action, verified, generation):
    from aos_api.extension_runtime.disable_service import RuntimeDisableService
    from aos_api.extension_runtime.disable_commit import begin_disable,finish_disable
    from aos_api.extension_runtime.disable_executor import RuntimeDisableExecutor
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.asset_registry.errors import AssetRegistryError
    permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION)
    dependent_calls=[]
    class Dependent:
        def after_runtime_fenced(self,conn,**context):
            dependent_calls.append(('fenced',context['runtime_operation_id']))
        def after_runtime_disabled(self,conn,**context):
            dependent_calls.append(('disabled',context['runtime_operation_id']))
    dependent=Dependent()
    service=RuntimeDisableService(installation_store=worker.store,installation_reader=reader,
        check_current_permission=permission,dependent=dependent)
    request=dict(**action,idempotency_key='signed-disable',if_match=f'"{verified.etag_version}"',
        target=dict(generation=str(generation),bindingRevision=4))
    from aos_api.extension_runtime.configuration_service import RuntimeConfigurationService
    with worker._connection(scope) as c:
        config=c.execute('SELECT config_ref FROM extension_runtime_binding').fetchone()['config_ref']
    stalled=RuntimeConfigurationService(installation_store=worker.store,installation_reader=reader,
        revalidator=worker.revalidator,authorize=worker.configuration_authorize).request(**action,kind='configure',
        idempotency_key='stalled-configure',if_match=f'"{verified.etag_version}"',
        target={**request['target'],'configRef':config})
    # Broken/expired dependencies cannot veto an authorized conservative fence.
    with worker.connect() as c:
        c.execute('UPDATE aip_budget_head SET current_revision=2')
    accepted=service.request(**request)
    assert accepted.status_code==202 and service.request(**request).replayed
    assert accepted.response_json['phase']=='fencing'
    assert [phase for phase,_ in dependent_calls]==['fenced']
    with worker._connection(scope) as c:
        assert c.execute('SELECT status FROM extension_runtime_operation WHERE operation_id=%s',
            (stalled.response_json['operationId'],)).fetchone()=={'status':'cancelled'}
        from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
        with pytest.raises(ValueError):
            RuntimeOperationStore().advance(c,**scope,operation_id=stalled.response_json['operationId'],expected_revision=2,phase='validating')
    with worker.connect() as c:c.execute("UPDATE meta_membership SET role='viewer'")
    with pytest.raises(AssetRegistryError):service.request(**request)
    with worker.connect() as c:c.execute("UPDATE meta_membership SET role='admin'")
    args=dict(**scope,operation_id=accepted.response_json['operationId'],expected_revision=1,
        installation_store=worker.store,check_current_permission=permission)
    with worker.connect() as c:
        c.execute('CREATE TABLE test_disable_work(generation uuid,epoch bigint,unresolved boolean)')
        c.execute('INSERT INTO test_disable_work VALUES(%s,3,true)',(generation,))
        c.execute('GRANT SELECT ON test_disable_work TO aos_runtime')
    # Fencing commits BEFORE any drain decision, so failure cannot reopen work.
    def pending(c,**context):
        assert context['generation']==str(generation) and context['fence_epoch'] in (4,5)
        # A different transaction already sees the fence when drain starts.
        with worker._connection(scope) as observer:
            assert observer.execute('SELECT enabled,operation_fence FROM extension_runtime_binding').fetchone()=={'enabled':False,'operation_fence':True}
        return c.execute('SELECT count(*) AS n FROM test_disable_work WHERE generation=%s AND unresolved',
            (context['generation'],)).fetchone()['n']==0
    @contextmanager
    def idle_connect():
        # This fixture owns the connection and finishes SET search_path setup;
        # never commit an unknown caller transaction in the production executor.
        with worker.connect() as c:
            c.commit()
            yield c
    executor=RuntimeDisableExecutor(connect=idle_connect,installation_store=worker.store,
        check_current_permission=permission,check_drained=pending,dependent=dependent)
    execute_args=dict(**scope,operation_id=accepted.response_json['operationId'],expected_revision=accepted.response_json['revision'])
    with pytest.raises(ValueError):executor.execute(**execute_args)
    args['expected_revision']=2
    for drain in (pending,lambda *a,**k:1):
        with pytest.raises(ValueError):
            with worker._connection(scope) as c:finish_disable(c,**args,check_drained=drain)
        with worker._connection(scope) as c:
            assert c.execute('SELECT enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()=={
                'enabled':False,'operation_fence':True,'observed_state':'draining'}
    with worker.connect() as c:c.execute('DELETE FROM test_disable_work')
    for failure in ('cas','etag','binding','fence','event','permission','async','rollback'):
        with pytest.raises((ValueError,PermissionError,AssetRegistryError)):
            with worker._connection(scope) as c:
                altered=dict(args)
                if failure=='cas':altered['expected_revision']=0
                if failure=='etag':c.execute('UPDATE extension_runtime_operation SET expected_installation_etag=expected_installation_etag+1 WHERE operation_id=%s',(args['operation_id'],))
                if failure=='binding':c.execute('UPDATE extension_runtime_binding SET revision=revision+1')
                if failure=='fence':c.execute('UPDATE extension_runtime_binding SET operation_fence=false')
                if failure=='event':
                    c.execute('UPDATE extension_runtime_operation SET revision=revision+1 WHERE operation_id=%s',(args['operation_id'],))
                    altered['expected_revision']=3
                if failure=='permission':altered['check_current_permission']=lambda **k:False
                drain=pending
                if failure=='async':
                    async def deferred(*a,**k):return True
                    drain=deferred
                finish_disable(c,**altered,check_drained=drain)
                if failure=='rollback':raise ValueError('isolated final-commit rollback')
        with worker._connection(scope) as c:
            assert c.execute('SELECT enabled,operation_fence FROM extension_runtime_binding').fetchone()=={'enabled':False,'operation_fence':True}
    result=executor.execute(**{**execute_args,'expected_revision':2})
    assert result.phase=='succeeded'
    assert [phase for phase,_ in dependent_calls]==['fenced','disabled']
    with worker._connection(scope) as c:
        assert c.execute('SELECT enabled,operation_fence,desired_state,observed_state,execution_epoch FROM extension_runtime_binding').fetchone()=={
            'enabled':False,'operation_fence':True,'desired_state':'disabled','observed_state':'unknown','execution_epoch':4}
        assert c.execute('SELECT observed_release FROM extension_runtime_resource_lease').fetchone()=={'observed_release':False}
    assert service.request(**request).replayed
    # The ordinary (non-preempting) command also fences in a distinct committed
    # transaction before the drain observer can see it; repeat never advances.
    normal=service.request(**{**request,'idempotency_key':'normal-disable',
        'target':dict(generation=str(generation),bindingRevision=6)})
    assert normal.response_json['phase']=='accepted'
    from aos_api.extension_runtime.disable_consumer import RuntimeDisableConsumer
    @contextmanager
    def consumer_connect():
        with worker.connect() as c:
            c.commit()
            c.execute('SET SESSION AUTHORIZATION aos_runtime')
            c.commit()
            yield c
    consumer=RuntimeDisableConsumer(connect=consumer_connect,installation_store=worker.store,
        check_current_permission=permission,check_drained=pending,dependent=dependent)
    normal_id=normal.response_json['operationId']
    original_ack=consumer.outbox.ack
    failed_lease=[]
    def fail_ack(c,**kwargs):
        original_ack(c,**kwargs)
        if str(kwargs['lease'].operation_id)==normal_id:
            failed_lease.append(kwargs['lease'])
            raise RuntimeError('isolated ACK transaction rollback')
    consumer.outbox.ack=fail_ack
    # Old terminal messages may precede this operation. They must not re-execute.
    for _ in range(30):
        try:consumer.run_once(**scope)
        except RuntimeError as exc:
            assert str(exc)=='isolated ACK transaction rollback'
            break
    assert len(failed_lease)==1
    assert [phase for phase,_ in dependent_calls]==['fenced','disabled','fenced','disabled']
    with worker._connection(scope) as c:
        before=c.execute('SELECT status,revision FROM extension_runtime_operation WHERE operation_id=%s',
            (normal_id,)).fetchone()
        assert before['status']=='succeeded'
        assert c.execute('SELECT delivered_at FROM extension_runtime_outbox WHERE event_id=%s',
            (failed_lease[0].event_id,)).fetchone()=={'delivered_at':None}
        # Expire only the exact isolated claim; force its retry ahead of later events.
        c.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second',next_attempt=clock_timestamp()-interval '1 day' WHERE event_id=%s",
            (failed_lease[0].event_id,))
    fresh=RuntimeDisableConsumer(connect=consumer_connect,installation_store=worker.store,
        check_current_permission=permission,check_drained=pending,dependent=dependent)
    def must_not_execute(**kwargs):raise AssertionError('terminal redelivery executed again')
    fresh.executor.execute=must_not_execute
    delivery=fresh.run_once(**scope)
    assert str(delivery.operation_id)==normal_id and delivery.operation_status=='succeeded'
    assert delivery.delivery_status=='acknowledged'
    for _ in range(30):
        if fresh.run_once(**scope) is None:break
    else:raise AssertionError('bounded disable event drain did not finish')
    with worker._connection(scope) as c:
        assert c.execute('SELECT status,revision FROM extension_runtime_operation WHERE operation_id=%s',
            (normal_id,)).fetchone()==before
        assert c.execute('SELECT delivered_at IS NOT NULL AS delivered FROM extension_runtime_outbox WHERE event_id=%s',
            (failed_lease[0].event_id,)).fetchone()=={'delivered':True}
        assert c.execute("SELECT count(*) AS n FROM extension_runtime_outbox b JOIN extension_runtime_event e USING(org_id,project_id,event_id) JOIN extension_runtime_operation o USING(org_id,project_id,operation_id) WHERE o.kind='disable' AND b.delivered_at IS NULL").fetchone()=={'n':0}
    assert [phase for phase,_ in dependent_calls]==['fenced','disabled','fenced','disabled']
    with worker._connection(scope) as c:
        assert c.execute('SELECT execution_epoch FROM extension_runtime_binding').fetchone()=={'execution_epoch':5}
