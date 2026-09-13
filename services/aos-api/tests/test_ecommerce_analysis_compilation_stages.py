from copy import deepcopy
from types import SimpleNamespace
import pytest
from aos_api import ecommerce_analysis_compilation_roles as module
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.ecommerce_business_investigation_aip_authority import build_stage_template_request
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('fault', [None, 'source', 'hash', 'revision', 'tenant', 'lifecycle',
                                  'readiness', 'legacy-profile', 'slots', 'order', 'deferred', 'drift'])
def test_stage_read_is_exact_and_inside_current_roles(monkeypatch, fault):
    scope = TenantScope('org-org', 'dev-project')
    request = build_stage_template_request()
    body = request.model_dump(mode='json', by_alias=True)
    body['profile'] = INITIAL_STORE_PROFILE.responsibility_template_code
    stage = dict(body, tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
                 templateId='template', revision=2, contentHash=canonical_hash(body),
                 lifecycle='frozen', readiness='ready')
    ref = ExactRevisionRef(resourceType='StageTemplateRevision', resourceId='template',
                           revision=2, contentHash=stage['contentHash'])
    slots = sorted({slot for item in request.stages for slot in item.required_slot_ids})
    role = {'responsibilityPlan': {'slots': [{'slotId': slot} for slot in slots]}}
    events = []
    reader = object.__new__(module.AnalysisCompilationRoleReader)
    def current(self, conn, **kw):
        events.append('role-enter')
        result = kw['execute'](deepcopy(role))
        events.append('role-exit')
        return result
    monkeypatch.setattr(module.AnalysisCompilationRoleReader, 'run_current', current)
    class Store:
        def __init__(self, *args, **kwargs): pass
        def get_stage_template(self, actual_scope, template_id, revision=None, *, conn):
            assert actual_scope == scope and template_id == ref.resource_id and revision is None
            events.append('stage-read')
            return SimpleNamespace(model_dump=lambda **kw: deepcopy(stage))
    monkeypatch.setattr(module, 'AipProductionContractStore', Store)
    if fault == 'source': stage['sourceBundleRef']['contentHash'] = 'b' * 64
    elif fault == 'hash': stage['contentHash'] = 'b' * 64
    elif fault == 'revision': stage['revision'] = 3
    elif fault == 'tenant': stage['tenant']['orgId'] = 'dev-org'
    elif fault == 'lifecycle': stage['lifecycle'] = 'draft'
    elif fault == 'readiness': stage['readiness'] = 'blocked'
    elif fault == 'legacy-profile':
        stage['profile'] = request.profile
        stage['contentHash'] = canonical_hash({key:stage[key] for key in ('profile','sourceBundleRef','stages')})
        ref = ref.model_copy(update={'content_hash':stage['contentHash']})
    elif fault == 'slots': role['responsibilityPlan']['slots'] = []
    elif fault == 'order': stage['stages'].reverse()
    def consume(value):
        events.append('consume')
        if fault == 'drift': stage['readiness'] = 'blocked'
        return value['stageTemplate']['templateId']
    def deferred(value): yield value
    def run():
        return reader.run_with_stage(object(), scope=scope, selection_ref={}, actor='actor',
            domain_profile=INITIAL_STORE_PROFILE, compiler_profile=INITIAL_STORE_PROFILE.responsibility_template_code,
            stage_ref=ref, execute=deferred if fault == 'deferred' else consume)
    if fault:
        with pytest.raises(ValueError): run()
        assert 'role-exit' not in events
    else:
        assert run() == 'template'
        assert events == ['role-enter', 'stage-read', 'consume', 'stage-read', 'role-exit']
