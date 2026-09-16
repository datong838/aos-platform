import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_a0v_l_successor_business import profile


@pytest.fixture
def cutover(profile, monkeypatch, tmp_path):
    successor, snapshot, parent = profile
    module = importlib.import_module('a0v_l_successor_cutover')
    request = successor.request_from(snapshot, parent)
    registration = {'outcome': 'CURRENT_L_SUCCESSOR_REGISTERED',
        'request': request.model_dump(mode='json', by_alias=True),
        'receipt': {'receiptId': module.RECEIPT, 'contentHash': module.RECEIPT_HASH,
                    'requestHash': request.request_hash()}}
    return module, registration


def test_target_is_exact_l_and_no_effect_policy(cutover):
    module, registration = cutover
    target, policy = module.target(registration)
    assert target['expectedGroupRevision'] == 35
    assert target['targetRuntimeRevision'] == 4
    assert target['targetInstallationId'] == module.successor.L_ID
    assert target['targetGeneration'] == module.successor.L_GENERATION
    assert len(target['operationIds']) == 9
    assert policy['externalEffectsAllowed'] is False
    assert policy['fallbackAllowed'] is False


@pytest.mark.parametrize('field', ['receiptId', 'contentHash', 'requestHash'])
def test_registration_receipt_drift_rejected(cutover, field):
    module, registration = cutover
    registration['receipt'][field] = 'changed'
    with pytest.raises(ValueError, match='exact L'):
        module.target(registration)


@pytest.mark.parametrize('phase', ['approve', 'prepare', 'pause', 'commit', 'validate', 'resume'])
def test_existing_phase_intent_never_invokes_service(cutover, monkeypatch, tmp_path, phase):
    module, _registration = cutover
    monkeypatch.setattr(module, 'STATE', tmp_path)
    (tmp_path / f'{phase}-intent.json').write_text('{}')
    with pytest.raises(ValueError, match='never resend'):
        module.invoke(phase, SimpleNamespace(ecommerce_growth_cutover_service=object()))


def test_exact_ref_rejects_other_cutover_operation(cutover, monkeypatch, tmp_path):
    module, _registration = cutover
    monkeypatch.setattr(module, 'STATE', tmp_path)
    (tmp_path / 'prepare-result.json').write_text(json.dumps({'receipt': {
        'cutoverOperationId': 'other', 'receiptId': 'receipt', 'contentHash': 'hash'}}))
    (tmp_path / 'prepare-result.json').chmod(0o600)
    with pytest.raises(ValueError, match='operation differs'):
        module.exact_ref('prepare', 'CutoverPrepareReceipt')
