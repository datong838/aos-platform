"""Named Owner fakes prove wiring only, never live source authority."""
from datetime import timedelta
from types import SimpleNamespace
import pytest

from test_ecommerce_product_event_policy import case
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_event_policy import ProductEventPolicyDraft
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v3 import SnapshotMappingV3
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_product_event_guard import ProductEventPolicyGuard


def fixture(version='v1'):
    body,record=case();context=ProductEventPolicyDraft.model_validate(body)
    policy=dict(schemaVersion='aos.ecommerce.product-event-schedule-policy/v1',
        tenant={'orgId':context.org_id,'projectId':context.project_id},schedulePolicyId=context.policy_id,
        sourceSelectionRef=context.source_selection_ref.model_dump(by_alias=True,mode='json'),
        platform=context.platform,shopId=context.shop_or_marketplace_id,objectTypes=list(context.object_types),
        effectiveFrom=context.effective_from.isoformat(),effectiveUntil=context.effective_until.isoformat(),
        maxSourceAgeSeconds=context.max_source_age_seconds,recoveryWindowSeconds=context.recovery_window_seconds)
    policy['contentHash']=canonical_sha256(policy)
    dispatch=SimpleNamespace(installation_id=context.installation_ref.installation_id,
        generation=context.generation,execution_epoch=context.execution_epoch)
    mapping=SnapshotMapping(record.read_spec,(),(),(),'niushop','site_id','1','+08:00',())
    if version == 'v3':
        mapping=SnapshotMappingV3(mapping,(),(),'state','state',((1,'ACTIVE'),))
    class Connection:
        now=context.effective_from
        def execute(self,query,params=()):
            assert 'clock_timestamp()' in query
            return SimpleNamespace(fetchone=lambda:{'now':self.now})
    conn=Connection();calls=[];owner=object.__new__(PipelineSourceSelectionOwner)
    def named_current(raw,*,scope,ref,actor,execute):
        assert raw is conn and ref==record.ref and actor=='fixture'
        calls.append('source-owner')
        return execute(record.draft,mapping)
    owner.run_current_snapshot=named_current
    return context,policy,dispatch,conn,calls,owner


def run(data,execute=lambda: 'saved'):
    context,policy,dispatch,conn,_,owner=data
    return ProductEventPolicyGuard(owner).run(transaction=HostTransaction(conn),
        scope=TenantScope(context.org_id,context.project_id),context=context,policy=policy,
        dispatch=dispatch,actor='fixture',execute=execute)


@pytest.mark.parametrize('version', ['v1','v3'])
def test_original_transaction_and_synchronous_result(version):
    data=fixture(version)
    assert run(data)=='saved' and data[4]==['source-owner']


@pytest.mark.parametrize('field',['shopId','schedulePolicyId','sourceSelectionRef','effectiveUntil','maxSourceAgeSeconds'])
def test_policy_drift_before_owner_callback(field):
    data=fixture();policy=data[1]
    policy[field]='different'
    policy['contentHash']=canonical_sha256({k:v for k,v in policy.items() if k!='contentHash'})
    with pytest.raises(ValueError):run(data,lambda:pytest.fail('must not execute'))
    assert not data[4]


def test_dispatch_epoch_drift_and_owner_denial():
    data=fixture();data[2].execution_epoch+=1
    with pytest.raises(ValueError):run(data)
    data=fixture()
    def denied(*a,**kw):raise PermissionError('current source denied')
    data[5].run_current_snapshot=denied
    with pytest.raises(PermissionError):run(data,lambda:pytest.fail('must not execute'))


@pytest.mark.parametrize('version', ['v1','v3'])
def test_expiry_before_and_during_callback(version):
    data=fixture(version);data[3].now=data[0].effective_until
    with pytest.raises(PermissionError):run(data,lambda:pytest.fail('must not execute'))
    data=fixture(version)
    def crosses_window():
        data[3].now=data[0].effective_until
        return 'pending'
    with pytest.raises(PermissionError):run(data,crosses_window)


def test_deferred_callback_rejected():
    data=fixture()
    async def deferred():return 'later'
    with pytest.raises(ValueError):run(data,deferred)


def test_policy_only_reconstructs_context_from_owner_once():
    data=fixture();context,policy,dispatch,conn,calls,owner=data
    result=ProductEventPolicyGuard(owner).run_policy(transaction=HostTransaction(conn),
        scope=TenantScope(context.org_id,context.project_id),policy=policy,dispatch=dispatch,
        actor='fixture',execute=lambda:'current')
    assert result=='current' and calls==['source-owner']


def test_policy_only_cannot_change_owner_scope_or_dispatch():
    data=fixture();context,policy,dispatch,conn,calls,owner=data
    dispatch.execution_epoch+=1
    with pytest.raises(ValueError):
        ProductEventPolicyGuard(owner).run_policy(transaction=HostTransaction(conn),
            scope=TenantScope(context.org_id,context.project_id),policy=policy,dispatch=dispatch,
            actor='fixture',execute=lambda:pytest.fail('must not execute'))
    assert calls==['source-owner']
