from types import SimpleNamespace
import pytest
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_business_investigation_aip_authority import build_responsibility_plan_request, _ROLE_BLUEPRINTS


@pytest.mark.parametrize('fault',[None,'readiness','coverage','template','template-id','compiler-profile','profile','duplicate','missing','hash','deferred'])
def test_role_reader_is_current_and_callback_bound(monkeypatch,fault):
    from aos_api import ecommerce_analysis_compilation_roles as module
    owner=object.__new__(PipelineSourceSelectionOwner);owner._authorization=object()
    scope=TenantScope('org-org','dev-project');events=[]
    draft=SimpleNamespace(org_id=scope.org_id,project_id=scope.project_id,
        installation_ref=SimpleNamespace(installation_id='installation'),generation='generation',execution_epoch=3,configuration_ref={})
    def current(self,conn,**kw):
        events.append('owner-enter');result=kw['execute'](draft,object());events.append('owner-exit');return result
    monkeypatch.setattr(PipelineSourceSelectionOwner,'run_current_snapshot',current)
    ref=SimpleNamespace(id='plan',revision=1,hash='sha256:'+'a'*64)
    document=SimpleNamespace(roleRefs=(ref,),model_dump=lambda **kw:{'role':'exact'})
    monkeypatch.setattr(module,'read_configuration',lambda *args,**kw:document)
    request=build_responsibility_plan_request({item[2]:1 for item in _ROLE_BLUEPRINTS})
    plan=dict(planId='plan',revision=1,contentHash='a'*64,profile=request.profile,lifecycle='frozen',
              readiness='ready',coverage='complete',slots=[slot.model_dump(mode='json',by_alias=True) for slot in request.slots],templateRef=request.template_ref.model_dump(mode='json',by_alias=True))
    class Store:
        def __init__(self,*args,**kwargs):pass
        def get_responsibility_plan(self,*args,**kw):
            events.append('read-role');return SimpleNamespace(model_dump=lambda **kw:dict(plan))
    monkeypatch.setattr(module,'AipProductionContractStore',Store)
    reader=module.AnalysisCompilationRoleReader(owner)
    if fault is not None:
        if fault=='readiness':plan['readiness']='blocked'
        elif fault=='coverage':plan['coverage']='partial'
        elif fault=='template':plan['templateRef']={**plan['templateRef'],'contentHash':'b'*64}
        elif fault=='template-id':plan['templateRef']={**plan['templateRef'],'resourceId':'unrelated'}
        elif fault=='profile':plan['profile']='unrelated'
        elif fault=='duplicate':document.roleRefs=(ref,ref)
        elif fault=='missing':document.roleRefs=()
        elif fault=='hash':plan['contentHash']='b'*64
        def deferred(value):yield 'outside-owner'
        with pytest.raises(ValueError):
            reader.run_current(object(),scope=scope,selection_ref={},actor='actor',domain_profile=INITIAL_STORE_PROFILE,
                compiler_profile='unrelated' if fault=='compiler-profile' else request.profile,execute=deferred if fault=='deferred' else lambda value:pytest.fail('unready role admitted'))
        assert 'owner-exit' not in events
        return
    def consume(value):events.append('consume');return value['responsibilityPlan']['planId']
    assert reader.run_current(object(),scope=scope,selection_ref={},actor='actor',domain_profile=INITIAL_STORE_PROFILE,
        compiler_profile=request.profile,execute=consume)=='plan'
    assert events==['owner-enter','read-role','consume','read-role','owner-exit']
    def mutate(value):plan['readiness']='blocked'
    with pytest.raises(ValueError):reader.run_current(object(),scope=scope,selection_ref={},actor='actor',
        domain_profile=INITIAL_STORE_PROFILE,compiler_profile=request.profile,execute=mutate)
