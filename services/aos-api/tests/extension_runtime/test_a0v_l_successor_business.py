import importlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    module = importlib.import_module('a0v_l_successor_business')
    snapshot = {
        'head': {'installation_id': module.L_ID, 'etag_version': 5, 'state': 'active',
                 'lock_hash': module.LOCK, 'overlay_revision': 'a0v-canonical-ecommerce-v1'},
        'bindings': [{'generation': module.L_GENERATION, 'revision': 4,
                      'execution_epoch': 3, 'enabled': True, 'operation_fence': False,
                      'desired_state': 'enabled', 'observed_state': 'ready',
                      'config_ref': deepcopy(module.CONFIG)}],
        'resources': [{'cleanup_state': 'pending', 'observed_release': False}
                      for _ in range(3)],
        'operations': [{'kind': kind, 'status': 'succeeded'} for kind in
                       ('runtime-apply', 'runtime-verify', 'configure', 'enable')],
        'canaryInstallations': 0,
    }
    authority = {'scope': 'final-j-detach'}
    parent = {'org_id': 'org-org', 'project_id': 'dev-project',
              'receipt_id': module.DETACH, 'phase': 'detach',
              'authority_data': authority, 'content_hash': canonical_sha256(authority)}
    monkeypatch.setattr(module, 'DETACH_HASH', parent['content_hash'])
    return module, snapshot, parent


@pytest.mark.parametrize('fault', ['installation', 'generation', 'revision', 'epoch',
    'enabled', 'fence', 'config', 'resource', 'operation', 'canary', 'parent', 'hash'])
def test_exact_l_and_parent_drift_rejected(profile, fault):
    module, snapshot, parent = profile
    binding = snapshot['bindings'][0]
    if fault == 'installation': snapshot['head']['installation_id'] = 'old'
    elif fault == 'generation': binding['generation'] = 'old'
    elif fault == 'revision': binding['revision'] = 5
    elif fault == 'epoch': binding['execution_epoch'] = 4
    elif fault == 'enabled': binding['enabled'] = False
    elif fault == 'fence': binding['operation_fence'] = True
    elif fault == 'config': binding['config_ref']['revision'] = 2
    elif fault == 'resource': snapshot['resources'][0]['observed_release'] = True
    elif fault == 'operation': snapshot['operations'][0]['status'] = 'accepted'
    elif fault == 'canary': snapshot['canaryInstallations'] = 1
    elif fault == 'parent': parent['receipt_id'] = 'other'
    elif fault == 'hash': parent['content_hash'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError):
        module.request_from(snapshot, parent)


def test_l_uses_current_group_and_final_j_detach(profile):
    module, snapshot, parent = profile
    request = module.request_from(snapshot, parent)
    assert request.expectedGroupRevision == 35
    assert str(request.registration.installationRef.installation_id) == module.L_ID
    assert str(request.registration.generation) == module.L_GENERATION
    assert request.predecessorDetachReceiptRef.resourceId == module.DETACH


def test_unknown_intent_only_reads_never_registers(profile, monkeypatch, tmp_path):
    module, snapshot, parent = profile
    monkeypatch.setattr(module, 'STATE', tmp_path)
    request = module.request_from(snapshot, parent)
    (tmp_path / 'register-intent.json').write_text(json.dumps(
        request.model_dump(mode='json', by_alias=True)))
    def forbidden(**_kwargs):
        pytest.fail('unknown outcome must not submit again')
    service = SimpleNamespace(register_successor=forbidden,
        read_successor_receipt=lambda **_kwargs: None)
    with pytest.raises(ValueError, match='readback'):
        module.register(SimpleNamespace(first_dispatch_registration_service=service), request)


def test_known_rollback_recovery_reuses_same_request_and_key(profile, monkeypatch, tmp_path):
    module, snapshot, parent = profile
    monkeypatch.setattr(module, 'STATE', tmp_path)
    request = module.request_from(snapshot, parent)
    material = request.model_dump(mode='json', by_alias=True)
    (tmp_path / 'register-intent.json').write_text(json.dumps(material))
    calls = []
    receipt = {'requestHash': request.request_hash(), 'replayed': False}
    service = SimpleNamespace(
        read_successor_receipt=lambda **_kwargs: None,
        register_successor=lambda **kwargs: calls.append(kwargs) or receipt)
    result = module.register(SimpleNamespace(first_dispatch_registration_service=service),
                             request, recover=True)
    assert result['receipt'] is receipt
    assert len(calls) == 1 and calls[0]['request'] == request
    assert calls[0]['request'].registration.idempotencyKey == module.KEY
