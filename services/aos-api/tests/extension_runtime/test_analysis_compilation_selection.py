from copy import deepcopy
import pytest
from test_ecommerce_analysis_start_operation import _package
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.ecommerce_analysis_compilation_roles import AnalysisCompilationRoleReader
from aos_api.tenant_scope import TenantScope
from aos_api.asset_registry.canonical_json import canonical_sha256


@pytest.mark.parametrize('fault',[None,'missing-stage','duplicate-stage','missing-skill','duplicate-skill','logic','drift'])
def test_selection_requires_unique_current_blueprint_dependencies(monkeypatch,fault):
    from aos_api import ecommerce_analysis_compilation_selection as module
    domain=INITIAL_STORE_PROFILE
    blueprint=_package().handle('ecommerce_growth_analysis_advance',dict(kind='build_analysis_compilation_blueprint',
        profileRef=domain.exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True)),object())
    stages=[dict(template_id='stage',revision=2,content_hash=canonical_sha256(blueprint['stageTemplateRequest']).removeprefix('sha256:'))]
    bindings=[dict(binding_id='binding-'+s['skillId'],skill_id=s['skillId']) for s in blueprint['stageSkills']]
    roles=object.__new__(AnalysisCompilationRoleReader);events=[]
    snapshot=dict(responsibilityPlan=dict(slots=[dict(assignee=dict(kind='agent_instance',resourceId='agent'))]))
    def within(self,conn,**kw):
        events.append('enter');result=kw['execute'](deepcopy(snapshot));events.append('exit');return result
    monkeypatch.setattr(AnalysisCompilationRoleReader,'run_current',within)
    class Skills:
        def __init__(self,reader):assert reader is roles
        def run_current(self,conn,**kw):
            data=dict(skills=[dict(skillId=s['skillId'],logicRevisionRef=dict(assetId='other' if fault=='logic' else s['canonicalLogicId'])) for s in blueprint['stageSkills']])
            return kw['execute'](data)
    monkeypatch.setattr(module,'AnalysisSkillSetReader',Skills)
    class Conn:
        def execute(self,sql,args):
            assert args[:2]==('org-org','dev-project')
            rows=stages if 'aip_stage_template_head' in sql else bindings
            class Result:
                def fetchall(self):return deepcopy(rows)
            return Result()
    if fault=='missing-stage':stages.clear()
    elif fault=='duplicate-stage':stages*=2
    elif fault=='missing-skill':bindings.pop()
    elif fault=='duplicate-skill':bindings.append(deepcopy(bindings[0]))
    def consume(value):
        events.append('consume')
        if fault=='drift':bindings.pop()
        return len(value['skills'])
    def run():return module.AnalysisCompilationSelectionReader(roles).run_current(Conn(),scope=TenantScope('org-org','dev-project'),
        selection_ref={},actor='actor',domain_profile=domain,blueprint=blueprint,execute=consume)
    if fault:
        with pytest.raises(ValueError):run()
        assert 'exit' not in events
    else:
        assert run()==3
        assert events==['enter','consume','exit']
