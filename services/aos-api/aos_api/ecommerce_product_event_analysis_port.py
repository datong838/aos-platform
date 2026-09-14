"""Installed growth START computation with exact caller/result correspondence."""
from copy import deepcopy
from datetime import datetime, timedelta

from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.ecommerce_growth_runtime_adapters import _analysis_exact_ref, _strict_analysis_start_command
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker


class InstalledProductEventAnalysisPort:
    def __init__(self, invoker):
        if type(invoker) is not CurrentInstalledPackageInvoker:
            raise TypeError('exact installed package invoker required')
        if invoker.package_id != 'solution.ecommerce.growth':
            raise ValueError('analysis start requires current growth package')
        self._invoker = invoker

    async def build_start(self, payload):
        fields = {'kind', 'occurrenceRef', 'caseRef', 'profileRef', 'cutoffAt', 'idempotencyKey'}
        if type(payload) is not dict or set(payload) != fields or payload['kind'] != 'build_analysis_start':
            raise ValueError('invalid analysis computation request')
        canonical_json(payload)
        snapshot = deepcopy(payload)
        for name, kind in [('occurrenceRef', 'AutomationOccurrence'),
                           ('caseRef', 'BusinessInvestigationCaseRevision'),
                           ('profileRef', 'InvestigationProfileRevision')]:
            value = snapshot[name]
            if type(value) is not dict or set(value) != {'resourceType', 'resourceId', 'revision', 'contentHash'}:
                raise ValueError('strict analysis reference required')
            _analysis_exact_ref(value, kind)
        key = snapshot['idempotencyKey']
        if type(key) is not str or not 1 <= len(key) <= 200 or key != key.strip() or not key.isprintable():
            raise ValueError('canonical analysis key required')
        if type(snapshot['cutoffAt']) is not str:
            raise ValueError('analysis cutoff must be canonical UTC seconds')
        cutoff = datetime.fromisoformat(snapshot['cutoffAt'])
        if cutoff.utcoffset() != timedelta(0) or cutoff.microsecond or cutoff.isoformat() != snapshot['cutoffAt']:
            raise ValueError('analysis cutoff must be canonical UTC seconds')
        if self._invoker.package_id != 'solution.ecommerce.growth':
            raise ValueError('analysis package changed')
        result = await self._invoker('ecommerce_growth_analysis_advance', deepcopy(snapshot))
        if self._invoker.package_id != 'solution.ecommerce.growth':
            raise ValueError('analysis package changed')
        _strict_analysis_start_command(result)
        if any(result[name] != snapshot[name] for name in fields - {'kind'}):
            raise ValueError('analysis command differs from current request')
        return deepcopy(result)

    async def build_compilation_blueprint(self, domain_profile):
        from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileRevision

        if type(domain_profile) is not EcommerceInvestigationProfileRevision:
            raise TypeError('exact domain investigation profile required')
        domain = EcommerceInvestigationProfileRevision.model_validate(domain_profile.model_dump(mode='json', by_alias=True))
        request = dict(kind='build_analysis_compilation_blueprint',
            profileRef=domain.exact_ref.model_dump(mode='json', by_alias=True, exclude_none=True))
        if self._invoker.package_id != 'solution.ecommerce.growth':
            raise ValueError('analysis package changed')
        result = await self._invoker('ecommerce_growth_analysis_advance', deepcopy(request))
        if self._invoker.package_id != 'solution.ecommerce.growth':
            raise ValueError('analysis package changed')
        return validate_analysis_compilation_blueprint(domain, result)


def validate_analysis_compilation_blueprint(domain_profile, result):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.aip_production_contracts import CreateStageTemplateRequest, ExactRevisionRef
    from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileRevision

    if type(domain_profile) is not EcommerceInvestigationProfileRevision:
        raise TypeError('exact domain profile required')
    domain = EcommerceInvestigationProfileRevision.model_validate(domain_profile.model_dump(mode='json', by_alias=True))
    request = dict(profileRef=domain.exact_ref.model_dump(mode='json', by_alias=True, exclude_none=True))
    fields = {'schemaVersion','profileRef','compilerProfile','stageTemplateRequest','stageSkills','contentHash',
              'startupContextPolicy'}
    if type(result) is not dict or set(result) != fields:
        raise ValueError('strict compilation blueprint response required')
    canonical_json(result)
    if (result['schemaVersion'] != 'aos.ecommerce.analysis-compilation-blueprint/v2'
            or canonical_json(result['profileRef']) != canonical_json(request['profileRef'])
            or result['compilerProfile'] != domain.responsibility_template_code
            or canonical_sha256({k:v for k,v in result.items() if k != 'contentHash'}) != result['contentHash']):
        raise ValueError('compilation blueprint differs from current domain request')
    stage = CreateStageTemplateRequest.model_validate(result['stageTemplateRequest'])
    source = ExactRevisionRef(resourceType=domain.exact_ref.resource_type,resourceId=domain.profile_id,
        revision=domain.revision,contentHash=domain.content_hash.removeprefix('sha256:'))
    order = tuple(item.stage_id for item in domain.stages)
    # This protocol supports startup lineage only. Business evidence is still
    # required by each analysis stage and cannot be asserted by the package.
    startup_policy = dict(schemaVersion='aos.ecommerce.analysis-startup-context-policy/v1',
        purpose='analysis-start',requiredFactIds=['analysis.original-event-case-run-lineage'],
        businessFactCoverage='not-evaluated',pendingFactProfilesSource='domain-profile.requiredFactProfiles',
        evalStageId=order[0],evalPurpose='skill-publication-contract')
    if canonical_json(result['startupContextPolicy']) != canonical_json(startup_policy):
        raise ValueError('unsupported analysis startup context policy')
    if (canonical_json(stage.model_dump(mode='json',by_alias=True)) != canonical_json(result['stageTemplateRequest'])
            or stage.profile != result['compilerProfile'] or stage.source_bundle_ref != source
            or tuple(item.stage_id for item in stage.stages) != order):
        raise ValueError('compilation stage definition differs from domain contract')
    selections = result['stageSkills']
    if (type(selections) is not list or len(selections) != len(order)
            or any(type(item) is not dict or set(item) != {'stageId','skillId','canonicalLogicId'} for item in selections)):
        raise ValueError('strict stage skill selection required')
    if tuple(item['stageId'] for item in selections) != order:
        raise ValueError('skill stage order differs')
    for key in ('skillId','canonicalLogicId'):
        values = [item[key] for item in selections]
        if (any(type(value) is not str or not 1 <= len(value) <= 200
                or value != value.strip() or not value.isprintable() for value in values)
                or len(values) != len(set(values))):
            raise ValueError('canonical unique stage dependency identities required')
    return deepcopy(result)
