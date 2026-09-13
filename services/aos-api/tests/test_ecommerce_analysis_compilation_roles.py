from types import SimpleNamespace
import pytest
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('fault',[None,'readiness','coverage','capabilities','duplicate','missing','hash','deferred'])
def test_role_reader_is_current_and_callback_bound(monkeypatch,fault):
    from aos_api import ecommerce_analysis_compilation_roles as module
    owner=object.__new__(PipelineSourceSelectionOwner);owner._authorization=object()
    scope=TenantScope('org-org','dev-project');events=[]
    draft=SimpleNamespace(org_id=scope.org_id,project_id=scope.project_id,
        installation_ref=SimpleNamespace(installation_id='installation'),generation='generation',configuration_ref={})
    def current(self,conn,**kw):
        events.append('owner-enter');result=kw['execute'](draft,object());events.append('owner-exit');return result
    monkeypatch.setattr(PipelineSourceSelectionOwner,'run_current_snapshot',current)
    ref=SimpleNamespace(id='plan',revision=1,hash='sha256:'+'a'*64)
    document=SimpleNamespace(roleRefs=(ref,),model_dump=lambda **kw:{'role':'exact'})
    monkeypatch.setattr(module,'read_configuration',lambda *args,**kw:document)
    plan=dict(planId='plan',revision=1,contentHash='a'*64,profile='ecommerce.analyst',lifecycle='frozen',
              readiness='ready',coverage='complete',slots=[{'requiredCapabilityIds':[c for s in INITIAL_STORE_PROFILE.stages for c in s.required_capability_ids]}])
    class Store:
        def __init__(self,*args):pass
        def get_responsibility_plan(self,*args,**kw):
            events.append('read-role');return SimpleNamespace(model_dump=lambda **kw:dict(plan))
    monkeypatch.setattr(module,'AipProductionContractStore',Store)
    reader=module.AnalysisCompilationRoleReader(owner)
    if fault is not None:
        if fault=='readiness':plan['readiness']='blocked'
        elif fault=='coverage':plan['coverage']='partial'
        elif fault=='capabilities':plan['slots']=[]
        elif fault=='duplicate':document.roleRefs=(ref,ref)
        elif fault=='missing':document.roleRefs=()
        elif fault=='hash':plan['contentHash']='b'*64
        def deferred(value):yield 'outside-owner'
        with pytest.raises(ValueError):
            reader.run_current(object(),scope=scope,selection_ref={},actor='actor',domain_profile=INITIAL_STORE_PROFILE,
                compiler_profile='ecommerce.analyst',execute=deferred if fault=='deferred' else lambda value:pytest.fail('unready role admitted'))
        assert 'owner-exit' not in events
        return
    def consume(value):events.append('consume');return value['responsibilityPlan']['planId']
    assert reader.run_current(object(),scope=scope,selection_ref={},actor='actor',domain_profile=INITIAL_STORE_PROFILE,
        compiler_profile='ecommerce.analyst',execute=consume)=='plan'
    assert events==['owner-enter','read-role','consume','read-role','owner-exit']
    def mutate(value):plan['readiness']='blocked'
    with pytest.raises(ValueError):reader.run_current(object(),scope=scope,selection_ref={},actor='actor',
        domain_profile=INITIAL_STORE_PROFILE,compiler_profile='ecommerce.analyst',execute=mutate)
