from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseCheck
from aos_api.ecommerce_growth_registration_qualification import (
    require_growth_registration_claims, qualify_registration_release,
)
import aos_api.ecommerce_growth_registration_qualification as module
from test_runtime_release_artifacts import selected as base_selected


def selected():
    path = Path(__file__).resolve().parents[4] / 'bundles/candidates/ecommerce/solution.ecommerce.growth/1.7.0/bundle.yaml'
    manifest = yaml.safe_load(path.read_text())
    payload = base_selected().model_dump(mode='json', by_alias=True)
    payload.update(id=manifest['metadata']['id'], version=manifest['metadata']['version'],
                   contributions=manifest['spec']['contributions'])
    return ResolvedBundle.model_validate(payload)


def test_current_candidate_declarations_are_complete_and_unchanged():
    value = selected()
    before = value.model_dump(mode='json', by_alias=True)
    assert require_growth_registration_claims(value).startswith('sha256:')
    assert value.model_dump(mode='json', by_alias=True) == before


@pytest.mark.parametrize('case', ['missing', 'duplicate', 'method', 'path', 'operation', 'extra-api', 'package', 'kind'])
def test_claim_drift_rejected(case):
    data = selected().model_dump(mode='json', by_alias=True)
    claims = data['contributions']
    index = next(i for i, item in enumerate(claims) if item['kind'] == 'api')
    if case == 'missing': claims.pop(index)
    elif case == 'duplicate': claims.append(deepcopy(claims[index]))
    elif case == 'method': claims[index]['method'] = 'GET'
    elif case == 'path': claims[index]['path'] = '/ecommerce/growth/other'
    elif case == 'operation': claims[index]['operationId'] = 'other_operation'
    elif case == 'extra-api':
        claims.append(dict(kind='api', method='POST', path='/other', operationId='other_operation', mode='exclusive'))
    elif case == 'package': data['id'] = 'solution.other'
    elif case == 'kind': data['kind'] = 'DomainPack'
    with pytest.raises(ValueError):
        require_growth_registration_claims(ResolvedBundle.model_validate(data))


@pytest.mark.parametrize('case', ['valid', 'missing-backend', 'wrong-hash', 'wrong-claims', 'revoked'])
def test_current_release_check_is_required_in_same_transaction(monkeypatch, case):
    value = selected()
    lock = SimpleNamespace(payload=SimpleNamespace(resolved=[value]), lock_hash='sha256:'+'a'*64)
    monkeypatch.setattr(module.StoredCompositionLock, 'model_validate', lambda _: lock)
    claims = (value.id, value.content_hash, require_growth_registration_claims(value))
    if case == 'wrong-hash': claims = (value.id, 'sha256:'+'b'*64, claims[2])
    if case == 'wrong-claims': claims = (value.id, value.content_hash, 'sha256:'+'b'*64)
    check = RuntimeReleaseCheck(datetime.now(timezone.utc), (value.id,),
                                backend_claim_fingerprints=() if case == 'missing-backend' else (claims,))
    calls = []
    def revalidate(self, conn, *, lock):
        calls.append((conn, lock))
        if case == 'revoked': raise PermissionError('revoked')
        return check
    monkeypatch.setattr(module.RuntimeReleaseRevalidator, 'revalidate_in_transaction', revalidate)
    conn = object()
    if case == 'valid':
        result = qualify_registration_release(conn, lock=lock, release_policy=ReleasePolicy(trust_roots=None))
        assert result['executable'] is False
        assert result['operationCount'] == 9
    else:
        with pytest.raises((ValueError, PermissionError)):
            qualify_registration_release(conn, lock=lock, release_policy=ReleasePolicy(trust_roots=None))
    assert calls == [(conn, lock)]


def test_arbitrary_release_policy_rejected():
    with pytest.raises(TypeError):
        qualify_registration_release(None, lock=None, release_policy=MagicMock())


def test_reordered_declarations_have_same_fingerprint():
    value = selected()
    data = value.model_dump(mode='json', by_alias=True)
    data['contributions'].reverse()
    assert require_growth_registration_claims(value) == require_growth_registration_claims(ResolvedBundle.model_validate(data))


def test_duplicate_non_api_declaration_is_rejected():
    data = selected().model_dump(mode='json', by_alias=True)
    item = next(c for c in data['contributions'] if c['kind'] != 'api')
    data['contributions'].append(deepcopy(item))
    with pytest.raises(ValueError, match='resolved contribution conflict keys must be unique'):
        require_growth_registration_claims(ResolvedBundle.model_validate(data))
