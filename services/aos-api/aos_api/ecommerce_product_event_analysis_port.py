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
