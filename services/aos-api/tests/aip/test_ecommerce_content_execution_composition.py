from types import SimpleNamespace
from datetime import UTC,datetime

import pytest

from aos_api.ecommerce_content_execution_composition import CurrentContentPreparation,CurrentContentContextReader,CurrentContentStatusReader
from aos_api.ecommerce_content_execution_journal import ContentExecutionConflict
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService,ReviewAdvanceHostService
from aos_api.aip_budget_reservation_contracts import BudgetExactRef,ReserveBudgetRequest
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal,_payload
import hashlib
from aos_api.aip_model_runtime_contracts import ModelRouteResolution
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore
from test_aip_budget_reservation_pg import content_generate_command


def method():
    ref = SimpleNamespace(resource_type='EvidenceBundleRevision',resource_id='bundle-1',
        revision=1,content_hash='a'*64)
    statement = lambda text: SimpleNamespace(text=text,evidence_refs=[ref])
    return SimpleNamespace(
        product_label='玫瑰面霜',audience_hypothesis=statement('干燥肤质客群'),
        scenario=statement('秋季护肤'),fit_for=[statement('需保湿体验')],
        not_fit_for=[statement('成分过敏者')],
        proposed_value_claims=[statement('可作为日常保湿方案')],
        unknown_facts=['即时库存'],prohibited_claims=['治疗疾病'],
        handoff_condition='先由人工核对成分与库存',channels=['微信小店'],
        time_window='九月第二周',evidence_refs=[ref],
    )


def test_prompt_is_bounded_and_keeps_unknown_and_prohibited_claims_explicit():
    prompt=CurrentContentPreparation._prompt(method(),max_input_tokens=2000)
    assert '玫瑰面霜' in prompt and '干燥肤质客群' in prompt
    assert '即时库存' in prompt and '治疗疾病' in prompt
    assert '人工评审' in prompt and 'E1' in prompt
    assert 'bundle-1' not in prompt
    with pytest.raises(ContentExecutionConflict,match='input token cap'):
        CurrentContentPreparation._prompt(method(),max_input_tokens=30)


def command():
    def ref(kind,identity):
        return BudgetExactRef(resourceType=kind,resourceId=identity,revision=1,
            contentHash='sha256:'+'a'*64)
    request=ReserveBudgetRequest(operationId='ecommerce_growth_content_generate',
        invocationKey='content-unit-1',taskRef=ref('Task','task-1'),
        policyRef=ref('BudgetRevision','budget-1'),
        pricingRef=ref('ModelPriceSnapshotRevision','price-1'),
        approvalRef=ref('ActionApprovalEvent','approval-1'),
        currency='CNY',upperBoundMinor=400)
    return content_generate_command(request)


def test_current_prepare_revalidates_before_creating_bounded_invocation(monkeypatch):
    item=command();scope=TenantScope('org-org','dev-project');calls=[]
    row={'request_hash':item['requestHash'],'response':{'state':'PENDING'},'runtime_revision':1}
    class Conn:
        def execute(self,query,params):
            calls.append('runtime-row')
            assert params[:2]==scope.key
            return SimpleNamespace(fetchone=lambda:row)
    snapshot=SimpleNamespace(runtime_revision=1,checked_at=datetime.now(UTC))
    monkeypatch.setattr(CurrentContentPreparation,'_lock_dispatch',
        staticmethod(lambda *_:calls.append('dispatch') or snapshot))
    monkeypatch.setattr(ContentGenerateHostService,'verify_receipt',
        lambda self,**kw:calls.append('receipt') or row['response'])
    monkeypatch.setattr(ContentGenerateHostService,'revalidate',
        lambda self,**kw:calls.append('host') or None)
    monkeypatch.setattr(ReviewAdvanceHostService,'_revalidate_growth_plan',
        staticmethod(lambda **kw:calls.append('plan') or SimpleNamespace(sales_weapon_method=method())))
    route=item['authorityRefs']['model_route'];price=item['authorityRefs']['pricing']
    resolution=ModelRouteResolution(tenant={'orgId':scope.org_id,'projectId':scope.project_id},
        route={'assetType':'ModelRouteRevision','assetId':route['resourceId'],'revision':1,
            'contentHash':route['contentHash'].removeprefix('sha256:')},
        policy={'assetType':'RuntimePolicyRevision','assetId':'policy','revision':1,'contentHash':'a'*64},
        readiness='ready',
        selectedModel={'assetType':'RegisteredModelRevision','assetId':'model','revision':1,'contentHash':'a'*64},
        selectedProvider={'assetType':'ProviderInstanceRevision','assetId':'provider','revision':1,'contentHash':'a'*64},
        selectedPriceSnapshot={'assetType':'ModelPriceSnapshotRevision','assetId':price['resourceId'],
            'revision':price['revision'],'contentHash':price['contentHash'].removeprefix('sha256:')},
        resolvedAt=datetime.now(UTC))
    monkeypatch.setattr(CurrentContentPreparation,'_resolve_route',
        staticmethod(lambda *_:calls.append('route') or resolution))
    prepared=CurrentContentPreparation()(Conn(),scope,item)
    assert calls==['runtime-row','dispatch','receipt','host','plan','route']
    assert prepared.max_output_tokens==item['maxOutputTokens']
    assert prepared.data_classification=='approved_internal_knowledge'
    assert '玫瑰面霜' in prepared.prompt


def test_prepare_without_current_pending_receipt_never_locks_dispatch(monkeypatch):
    item=command();scope=TenantScope('org-org','dev-project')
    class Conn:
        def execute(self,*_):return SimpleNamespace(fetchone=lambda:None)
    monkeypatch.setattr(CurrentContentPreparation,'_lock_dispatch',
        staticmethod(lambda *_:pytest.fail('dispatch must not be entered')))
    with pytest.raises(ContentExecutionConflict,match='PENDING Receipt unavailable'):
        CurrentContentPreparation()(Conn(),scope,item)


def test_result_context_uses_exact_approved_plan_and_agent_task_run(monkeypatch):
    item=command();scope=TenantScope('org-org','dev-project');seen=[]
    class Conn:
        def execute(self,query,params):
            seen.append(params)
            return SimpleNamespace(fetchone=lambda:{'task_id':item['authorityRefs']['task']['resourceId'],
                'run_id':'run-1','run_task_id':item['authorityRefs']['task']['resourceId']})
    monkeypatch.setattr(EcommerceAnalystAuthorityStore,'get_plan_exact',
        lambda self,read_scope,ref:SimpleNamespace(sales_weapon_method=method(),
            lifecycle='approved'))
    context=CurrentContentContextReader()(Conn(),scope,item)
    assert context['runId']=='run-1'
    assert context['productNames']==['玫瑰面霜']
    assert context['channels']==['微信小店']
    assert any('待核' in value for value in context['constraintChecks'])
    assert any('禁止' in value for value in context['constraintChecks'])
    assert seen[0][:2]==scope.key


def test_runner_pass_drains_old_result_before_new_send_and_then_new_result():
    from aos_api.ecommerce_content_execution_composition import CurrentContentRunner
    runner=object.__new__(CurrentContentRunner)
    calls=[]
    runner.run_recorded=lambda scope,limit=32:calls.append('recorded') or []
    runner.run_pending=lambda scope,limit=32:calls.append('pending') or []
    assert runner.run_once(TenantScope('org-org','dev-project'))=={
        'recordedBefore':[],'pending':[],'recordedAfter':[]}
    assert calls==['recorded','pending','recorded']


@pytest.mark.parametrize('state,expected',[('settled','COMPLETED'),('cost_pending','COST_PENDING')])
def test_status_requires_independent_artifact_usage_and_provider_readback(monkeypatch,state,expected):
    scope=TenantScope('org-org','dev-project')
    invocation='00000000-0000-0000-0000-000000000001'
    result={'answer':'可读草稿'};result_hash=_payload(result)[1]
    artifact_id='artifact-'+hashlib.sha256(invocation.encode()).hexdigest()[:20]
    content={'body':'可读草稿','sourceArtifactRefs':[]}
    digest=canonical_hash(content)
    artifact_ref={'resourceType':'ArtifactRevision','resourceId':artifact_id,
        'revision':1,'contentHash':'sha256:'+digest}
    usage=[];refs=[]
    for index,kind in enumerate(('input_token','output_token')):
        item={'receipt_id':f'usage-{index}','provider':'provider','provider_receipt_id':f'receipt-{index}',
            'lineage_id':invocation,'usage_kind':kind,'quantity':1,'unit':'token','currency':None,
            'quality':'measured','source_hash':result_hash,'observed_at':datetime.now(UTC)}
        usage.append(item)
        refs.append({'resourceType':'UsageReceipt','resourceId':item['receipt_id'],
            'revision':1,'contentHash':canonical_hash(item,prefixed=True)})
    row={'operation_id':'ecommerce_growth_content_generate','state':state,'invocation_id':invocation,
        'task_ref':{'resourceId':'task-1'},
        'provider_request_receipt_ref':{'resourceId':'request','revision':1,'contentHash':'sha256:'+'a'*64},
        'provider_receipt_ref':{'resourceId':'provider-receipt','revision':1,'contentHash':'sha256:'+'b'*64},
        'usage_receipt_refs':refs}
    data=[row,{'request_receipt_id':'request','revision':1,'content_hash':'sha256:'+'a'*64},
        {'provider_receipt_id':'provider-receipt','revision':1,'content_hash':'sha256:'+'b'*64,
            'provider_result_hash':result_hash,'outcome':'completed','evidence_refs':[artifact_ref]},
        {'artifact_id':artifact_id,'run_id':'run','artifact_type':'ecommerce_content',
            'schema_ref':'aos://schemas/ecommerce-readable-content/v1','content_hash':digest,
            'metadata':{'ecommerceGrowthContentArtifact':{**content,'artifactRef':artifact_ref}},
            'source':{'invocationId':invocation,'providerResultHash':result_hash}},
        {'task_id':'task-1'},*usage]
    class Conn:
        def execute(self,*_):return SimpleNamespace(fetchone=lambda:data.pop(0))
    monkeypatch.setattr(ContentExecutionJournal,'read',lambda *_:{'command':{},'result':result})
    assert CurrentContentStatusReader()(Conn(),scope,'reservation')==expected
    data=[row,{'request_receipt_id':'request','revision':1,'content_hash':'sha256:'+'a'*64},
        {'provider_receipt_id':'provider-receipt','revision':1,'content_hash':'sha256:'+'b'*64,
            'provider_result_hash':result_hash,'outcome':'completed','evidence_refs':[artifact_ref]},
        None]
    with pytest.raises(ContentExecutionConflict,match='Artifact readback'):
        CurrentContentStatusReader()(Conn(),scope,'reservation')
