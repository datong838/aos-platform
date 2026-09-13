from copy import deepcopy
from types import SimpleNamespace
import pytest
from test_ecommerce_analysis_skill_set import data
from aos_api.ecommerce_analysis_compilation_roles import AnalysisCompilationRoleReader
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('fault',[None,'assignee','readiness','dependency','publication','logic','drift','deferred'])
def test_current_skill_reader_stays_inside_role_boundary(monkeypatch,fault):
    from aos_api import ecommerce_analysis_skill_reader as module
    now,binding,payload=data()
    role=object.__new__(AnalysisCompilationRoleReader)
    events=[]
    snapshot=dict(currentInstallation={k:payload[k] for k in ('installationId','generation','executionEpoch')},
        responsibilityPlan=dict(planId='plan',revision=2,contentHash='c'*64,
            slots=[dict(assignee=dict(kind='agent_instance',resourceId='agent'))]))
    def within(self,conn,**kw):
        events.append('enter');result=kw['execute'](deepcopy(snapshot));events.append('exit');return result
    monkeypatch.setattr(AnalysisCompilationRoleReader,'run_with_stage',within)
    skill=dict(skillId='skill',revision=2,contentHash='a'*64,lifecycle='published',
        publicationTenant=payload['tenant'],logicRevisionRef=dict(assetType='LogicRevision',assetId='logic',revision=1,contentHash='d'*64))
    class Registry:
        def __init__(self,*a,**kw):pass
        def get_binding(self,*a):return binding
        def get_skill(self,*a):return SimpleNamespace(model_dump=lambda **kw:deepcopy(skill))
    class Readiness:
        def __init__(self,*a,**kw):pass
        def evaluate(self,*a,**kw):return SimpleNamespace(readiness=SimpleNamespace(value='blocked' if fault=='readiness' else 'available'),
            reasons=[],dependency_snapshot_hash='x'*64 if fault=='dependency' else binding.dependency_snapshot_hash)
    monkeypatch.setattr(module,'AipSkillRegistry',Registry)
    monkeypatch.setattr(module,'AipSkillBindingReadinessService',Readiness)
    class Conn:
        def execute(self,sql,args=()):
            if 'clock_timestamp' in sql:return SimpleNamespace(fetchone=lambda:dict(now=now))
            return SimpleNamespace(fetchall=lambda:[] if fault=='logic' else [dict(publication_id='publication',graph_hash='d'*64)])
    if fault=='assignee':snapshot['responsibilityPlan']['slots']=[]
    if fault=='publication':skill['publicationTenant']={**payload['tenant'],'orgId':'dev-org'}
    def consume(value):
        events.append('consume')
        if fault=='drift':binding.version+=1
        return value['skillBindingSetRef']['resourceType']
    def deferred(value):yield value
    def run():return module.AnalysisSkillSetReader(role).run_current(Conn(),scope=TenantScope('org-org','dev-project'),
        selection_ref={},actor='actor',domain_profile=INITIAL_STORE_PROFILE,compiler_profile=INITIAL_STORE_PROFILE.responsibility_template_code,
        stage_ref=object(),binding_ids=['binding'],execute=deferred if fault=='deferred' else consume)
    if fault:
        with pytest.raises(ValueError):run()
        assert 'exit' not in events
    else:
        assert run()=='SkillBindingSetRevision'
        assert events==['enter','consume','exit']
