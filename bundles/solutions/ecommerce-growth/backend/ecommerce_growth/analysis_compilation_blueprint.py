"""Package-owned compilation intent; runtime dependencies remain Host authorities."""
from copy import deepcopy
import hashlib
import json

_PROFILE = dict(resourceType='InvestigationProfileRevision', resourceId='ecommerce.initial-store-analysis',
    revision=1, contentHash='sha256:267e3ec1a06662793ef1c71a7a70cc4952fbe3833e910caa63bc8e5399ae96fb')
_COMPILER_PROFILE = 'ecommerce.business-investigation.readonly'
_STAGES = (
    ('portrait', '经营画像', (), ('investigation-owner','data-steward','content-research','customer-research','channel-research'), 'D01'),
    ('diagnosis', '问题与机会诊断', ('portrait',), ('investigation-owner','data-steward','customer-research','channel-research','business-reviewer'), 'D02'),
    ('solution-design', '方案设计', ('diagnosis',), ('investigation-owner','content-research','channel-research','business-reviewer'), 'D03'),
)


def build_analysis_compilation_blueprint(payload):
    if type(payload) is not dict or set(payload) != {'kind','profileRef'} or payload['kind'] != 'build_analysis_compilation_blueprint':
        raise ValueError('strict compilation blueprint request required')
    ref = payload['profileRef']
    if type(ref) is not dict or ref != _PROFILE or type(ref.get('revision')) is not int:
        raise ValueError('unsupported exact investigation profile')

    def schema(stage, direction):
        return dict(resourceType='JsonSchema', resourceId=f'business-investigation.{stage}.{direction}',
                    revision='1', authority='aos.ecommerce.business-investigation')

    stages = [dict(stageId=stage, title=title, dependsOn=list(dependencies),
        applicability=dict(kind='always',profiles=[]), requiredSlotIds=list(slots),
        inputSchemaRef=schema(stage,'input'), outputSchemaRef=schema(stage,'output'), gateRefs=[],
        checkpointPolicy=dict(mode='receipt-first',unknown='pause'), retryPolicy=dict(automatic=False),
        compensationPolicy=dict(externalEffect='none')) for stage,title,dependencies,slots,_ in _STAGES]
    source = {**_PROFILE, 'contentHash': _PROFILE['contentHash'].removeprefix('sha256:')}
    body = dict(schemaVersion='aos.ecommerce.analysis-compilation-blueprint/v2', profileRef=deepcopy(_PROFILE),
        compilerProfile=_COMPILER_PROFILE,
        startupContextPolicy=dict(schemaVersion='aos.ecommerce.analysis-startup-context-policy/v1',
            purpose='analysis-start',requiredFactIds=['analysis.original-event-case-run-lineage'],
            businessFactCoverage='not-evaluated',pendingFactProfilesSource='domain-profile.requiredFactProfiles',
            evalStageId='portrait',evalPurpose='skill-publication-contract'),
        stageTemplateRequest=dict(profile=_COMPILER_PROFILE,sourceBundleRef=source,stages=stages),
        stageSkills=[dict(stageId=stage,skillId=f'ecommerce.skill.{skill}',canonicalLogicId=f'ecommerce.logic.{skill}')
                     for stage,_,_,_,skill in _STAGES])
    encoded = json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return {**body,'contentHash':'sha256:'+hashlib.sha256(encoded).hexdigest()}
