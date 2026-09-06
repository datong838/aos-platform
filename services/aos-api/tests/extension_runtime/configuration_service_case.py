"""Signed live-owner service integration, only the caller's isolated schema."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager
import importlib.util

import pytest


def exercise_configuration_service(connect,store,reader,validator,scope,action,verified,generation):
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.asset_registry.control_policy import CONFIGURE_RUNTIME_OPERATION
    from aos_api.asset_registry.errors import AssetRegistryError
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.configuration_service import RuntimeConfigurationService
    from aos_api.extension_runtime.configuration_store import append_configuration
    from aos_api.extension_runtime.configuration_consumer import ConfigurationConsumer
    from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
    from current_configuration_sources_case import install_current_configuration_sources
    path=Path(__file__).resolve().parents[2]/'alembic/versions/ar1_002_runtime_configuration.py'
    spec=importlib.util.spec_from_file_location('signed_configuration_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with connect() as c:
        migration.op=SimpleNamespace(execute=c.execute);migration.upgrade()
        schema=c.execute('SELECT current_schema() AS schema').fetchone()['schema']
        _,sources=install_current_configuration_sources(c,schema)
        document=sources['configuration']

    def permission(c,*,installation_id,actor,**_):
        etag=c.execute('SELECT etag_version FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s',
            (scope['org_id'],scope['project_id'],installation_id)).fetchone()['etag_version']
        locked=store.lock_for_transition_in_transaction(c,**scope,installation_id=installation_id,expected_etag_version=etag)
        return CurrentControlPermission(operation=CONFIGURE_RUNTIME_OPERATION)(conn=c,locked=locked,actor=actor)
    authorize=build_current_configuration_authorization(permission=permission)
    write=dict(**scope,installation_id=verified.installation_id,generation=str(generation),actor=action['actor'],
        expected_installation_etag=verified.etag_version,expected_binding_revision=1,
        idempotency_key='signed-config-version',configuration=document,authorize=authorize)
    with connect() as c:
        with pytest.raises(ValueError):
            with c.transaction():
                c.execute("""INSERT INTO aip_responsibility_plan_revision
                    (org_id,project_id,plan_id,revision,profile,template_ref,slots,merge_decisions,
                     profile_recommendation_ref,profile_confirmation_id,merge_policy_ref,
                     merge_decision_receipt_ids,content_hash,lifecycle,created_by,created_at)
                    SELECT org_id,project_id,plan_id,2,profile,template_ref,slots,merge_decisions,
                           profile_recommendation_ref,'drifted-confirmation',merge_policy_ref,
                           merge_decision_receipt_ids,content_hash,lifecycle,created_by,created_at
                      FROM aip_responsibility_plan_revision WHERE revision=1""")
                c.execute('UPDATE aip_responsibility_plan_head SET current_revision=2')
                drifted_role=document.roleRefs[0].model_copy(update={'revision':2})
                drifted=document.model_copy(update={'roleRefs':(drifted_role,)})
                apply_asset_transaction_scope(c,**scope)
                append_configuration(c,**{**write,'idempotency_key':'governance-drift',
                    'configuration':drifted})
    with connect() as c:
        apply_asset_transaction_scope(c,**scope)
        first=append_configuration(c,**write)
    service=RuntimeConfigurationService(installation_store=store,installation_reader=reader,revalidator=validator,authorize=authorize)
    target=dict(generation=str(generation),bindingRevision=1,configRef=first.model_dump(mode='json'))
    request=dict(**action,kind='configure',idempotency_key='signed-configure',if_match=f'"{verified.etag_version}"',target=target)
    accepted=service.request(**request)
    assert accepted.status_code==202
    assert service.request(**request).replayed
    with pytest.raises(ValueError):service.request(**{**request,'idempotency_key':'competing-configure'})
    with connect() as c:c.execute("UPDATE meta_membership SET role='viewer'")
    with pytest.raises(AssetRegistryError):service.request(**request)
    with connect() as c:c.execute("UPDATE meta_membership SET role='admin'")
    @contextmanager
    def consumer_connect():
        with connect() as c:
            # This fixture owns the search_path setup transaction and connection.
            c.commit()
            c.execute('SET SESSION AUTHORIZATION aos_runtime')
            c.commit()
            yield c
    operation_id=accepted.response_json['operationId']
    def state():
        with connect() as c:
            return (c.execute('SELECT status,revision FROM extension_runtime_operation WHERE operation_id=%s',
                (operation_id,)).fetchone(),c.execute('SELECT enabled,operation_fence,execution_epoch,revision,config_ref FROM extension_runtime_binding').fetchone())
    drain_ready=False
    def drained(c,**kwargs):
        # A different connection must see the fence before drain is attempted.
        observed=state()[1]
        assert observed['operation_fence'] and not observed['enabled'] and observed['execution_epoch']==2
        # Named fixture seam, not proof of the production broker's drain state.
        return drain_ready
    consumer=ConfigurationConsumer(connect=consumer_connect,authorize=authorize,check_drained=drained)
    with pytest.raises(ValueError):consumer.run_once(**scope)
    assert state()[1]['execution_epoch']==2
    with connect() as c:
        c.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second' WHERE event_id IN (SELECT event_id FROM extension_runtime_event WHERE operation_id=%s) AND claim_until IS NOT NULL",(operation_id,))
        c.execute('UPDATE aip_responsibility_plan_head SET current_revision=2 WHERE plan_id=%s',
            (document.roleRefs[0].id,))
    fenced_state=state()
    drain_ready=True
    with pytest.raises((ValueError,LookupError),match='responsibility plan (reference is no longer current|unavailable)'):
        consumer.run_once(**scope)
    assert state()==fenced_state
    with connect() as c:
        c.execute('UPDATE aip_responsibility_plan_head SET current_revision=1 WHERE plan_id=%s',
            (document.roleRefs[0].id,))
        c.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second' WHERE event_id IN (SELECT event_id FROM extension_runtime_event WHERE operation_id=%s) AND claim_until IS NOT NULL",(operation_id,))
        c.execute('UPDATE aip_budget_head SET current_revision=2 WHERE budget_id=%s',(document.budgetRef.id,))
    fenced_state=state()
    drain_ready=True
    with pytest.raises(ValueError,match='budget reference is no longer current'):consumer.run_once(**scope)
    assert state()==fenced_state
    with connect() as c:
        # Fault injection restoration only; never a production budget rollback.
        c.execute('UPDATE aip_budget_head SET current_revision=1 WHERE budget_id=%s',(document.budgetRef.id,))
        c.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second' WHERE event_id IN (SELECT event_id FROM extension_runtime_event WHERE operation_id=%s) AND claim_until IS NOT NULL",(operation_id,))
    drain_ready=True
    original_ack=consumer.outbox.ack
    lost=[]
    def fail_ack(c,**kwargs):
        original_ack(c,**kwargs)
        lost.append(kwargs['lease'])
        raise RuntimeError('named configuration ACK rollback')
    consumer.outbox.ack=fail_ack
    with pytest.raises(RuntimeError,match='named configuration ACK rollback'):consumer.run_once(**scope)
    before=state()
    assert before[0]['status']=='succeeded' and before[1]['execution_epoch']==2 and len(lost)==1
    with connect() as c:
        assert c.execute('SELECT delivered_at FROM extension_runtime_outbox WHERE event_id=%s',(lost[0].event_id,)).fetchone()=={'delivered_at':None}
        c.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second',next_attempt=clock_timestamp()-interval '1 day' WHERE event_id=%s",(lost[0].event_id,))
    def forbidden(*args,**kwargs):raise AssertionError('committed configuration replayed')
    fresh=ConfigurationConsumer(connect=consumer_connect,authorize=forbidden,check_drained=forbidden)
    result=fresh.run_once(**scope)
    assert str(result.operation_id)==str(operation_id) and result.delivery_status=='acknowledged'
    for _ in range(30):
        if fresh.run_once(**scope) is None:break
    else:raise AssertionError('bounded configuration event drain did not finish')
    assert state()==before
    with connect() as c:
        apply_asset_transaction_scope(c,**scope)
        second=append_configuration(c,**{**write,'expected_binding_revision':3,'idempotency_key':'second-signed-config'},previous_ref=first)
        assert c.execute('SELECT enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()=={
            'enabled':False,'operation_fence':True,'observed_state':'unknown'}
    target.update(bindingRevision=3)
    enable={**request,'kind':'enable','idempotency_key':'signed-enable','target':target}
    with pytest.raises(ValueError):service.request(**{**enable,'target':{**target,'configRef':second.model_dump(mode='json')}})
    enabled=service.request(**enable)
    assert enabled.status_code==202
    assert service.request(**enable).replayed
    with connect() as c:
        assert c.execute('SELECT count(*) AS count FROM aip_budget_receipt').fetchone()=={'count':0}
    return dict(authorize=authorize,operation_id=enabled.response_json['operationId'],expected_revision=enabled.response_json['revision'])
