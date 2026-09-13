from copy import deepcopy
from pathlib import Path
import sys

import pytest


def _package():
    root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(root / 'bundles/solutions/ecommerce-growth/backend'))
    sys.path.insert(0, str(root / 'packages/aos-extension-sdk/python'))
    try:
        import ecommerce_growth
        import ecommerce_growth.analysis_start_operation
        return ecommerce_growth
    finally:
        del sys.path[:2]


def _request():
    def ref(kind):
        return dict(resourceType=kind, resourceId='id', revision=1, contentHash='sha256:'+'a'*64)
    return dict(kind='build_analysis_start', occurrenceRef=ref('AutomationOccurrence'),
                caseRef=ref('BusinessInvestigationCaseRevision'), profileRef=ref('InvestigationProfileRevision'),
                cutoffAt='2026-09-14T00:00:00+00:00', idempotencyKey='automation-occurrence:id')


def test_installed_start_command_matches_existing_host_contract():
    from aos_api.ecommerce_growth_runtime_adapters import _strict_analysis_start_command
    request = _request()
    original = deepcopy(request)
    package = _package()
    result = package.handle('ecommerce_growth_analysis_advance', request, object())
    _strict_analysis_start_command(result)
    assert package.handle('ecommerce_growth_analysis_advance', request, object()) == result
    assert result['operation'] == 'runtime.analysis.start'
    assert request == original


@pytest.mark.parametrize('fault', ['extra', 'blank-key', 'key-space', 'naive', 'subsecond', 'wrong-ref', 'bool-revision', 'receipt'])
def test_installed_start_command_rejects_invalid_input(fault):
    request = _request()
    if fault == 'extra': request['approved'] = True
    elif fault == 'blank-key': request['idempotencyKey'] = ''
    elif fault == 'key-space': request['idempotencyKey'] += ' '
    elif fault == 'naive': request['cutoffAt'] = '2026-09-14T00:00:00'
    elif fault == 'subsecond': request['cutoffAt'] = '2026-09-14T00:00:00.123+00:00'
    elif fault == 'wrong-ref': request['caseRef']['resourceType'] = 'TaskRun'
    elif fault == 'bool-revision': request['caseRef']['revision'] = True
    else: request['caseRef']['receiptId'] = 'not-case-authority'
    with pytest.raises(ValueError):
        _package().handle('ecommerce_growth_analysis_advance', request, object())
