from datetime import UTC, datetime, timedelta
from uuid import UUID
import pytest
from aos_api.aip_agent_registry_contracts import SkillBinding
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.tenant_scope import TenantScope


def data():
    now=datetime(2026,9,14,tzinfo=UTC)
    asset=dict(assetType='SkillTemplate',assetId='skill',revision=2,contentHash='a'*64)
    binding=SkillBinding(tenant=dict(orgId='org-org',projectId='dev-project'),bindingId='binding',instanceId='agent',
        skill=asset,capabilityBindingIds=['capability'],budgetPolicyRef={**asset,'assetType':'BudgetPolicy','assetId':'budget'},
        readiness='available',readinessReasons=[],dependencySnapshotHash='b'*64,lastEvaluatedAt=now-timedelta(minutes=1),
        readinessExpiresAt=now+timedelta(minutes=1),status='active',version=2,createdAt=now,updatedAt=now)
    payload=dict(tenant=binding.tenant.model_dump(mode='json',by_alias=True),installationId=str(UUID(int=1)),
        generation=str(UUID(int=2)),executionEpoch=3,
        responsibilityPlanRef=dict(resourceType='ResponsibilityPlanRevision',resourceId='plan',revision=2,contentHash='c'*64),
        bindings=[binding.model_dump(mode='json',by_alias=True)])
    return now,binding,payload


@pytest.mark.parametrize('fault',[None,'expiry','revoked','changed','tenant','generation','duplicate','hash','unready','unevaluated','future','no-dependency','reason'])
def test_skill_set_requires_current_exact_authority(fault):
    from aos_api.ecommerce_analysis_skill_set import AnalysisSkillBindingSet
    now,binding,payload=data()
    changes={'unready':{'readiness':'unknown'},'unevaluated':{'last_evaluated_at':None},
        'future':{'last_evaluated_at':now+timedelta(seconds=1)},
        'no-dependency':{'dependency_snapshot_hash':None},'reason':{'readiness_reasons':['blocked']}}
    if fault in changes:
        binding=SkillBinding.model_validate({**binding.model_dump(),**changes[fault]})
        payload['bindings']=[binding.model_dump(mode='json',by_alias=True)]
    payload['schemaVersion']='aos.ecommerce.analysis-skill-binding-set/v1'
    if fault=='duplicate':payload['bindings']*=2
    payload['contentHash']=canonical_sha256(payload)
    if fault=='hash':payload['contentHash']='sha256:'+'f'*64
    if fault in ('duplicate','hash'):
        with pytest.raises(ValueError):AnalysisSkillBindingSet.model_validate(payload)
        return
    snapshot=AnalysisSkillBindingSet.model_validate(payload)
    args=dict(scope=TenantScope('org-org','dev-project'),installation_id=UUID(int=1),generation=UUID(int=2),
        execution_epoch=3,responsibility_ref=ExactRevisionRef.model_validate(payload['responsibilityPlanRef']),
        bindings=[binding],now=now)
    if fault=='expiry':args['now']=now+timedelta(minutes=1)
    elif fault=='revoked':args['bindings']=[binding.model_copy(update={'status':'disabled'})]
    elif fault=='changed':args['bindings']=[binding.model_copy(update={'version':3})]
    elif fault=='tenant':args['scope']=TenantScope('dev-org','dev-project')
    elif fault=='generation':args['generation']=UUID(int=3)
    if fault:
        with pytest.raises(ValueError):snapshot.validate_current(**args)
    else:
        assert snapshot.validate_current(**args)==snapshot.exact_ref
        assert snapshot.exact_ref.resource_type=='SkillBindingSetRevision'
        snapshot.bindings[0].version=8
        with pytest.raises(ValueError):snapshot.validate_current(**args)
