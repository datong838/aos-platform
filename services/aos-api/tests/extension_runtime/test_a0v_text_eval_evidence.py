from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from a0v_text_eval_evidence import read_verified_text_evidence, expected_identity, TextEvidenceBlocked
from a0v_exact_text_live_eval import CASES
from aos_api.aip_agent_registry_contracts import VersionedAssetRef

NOW = datetime(2026, 9, 11, 4, tzinfo=UTC)
PROVIDER = VersionedAssetRef(assetType='ProviderInstanceRevision', assetId='p', revision=1, contentHash='a'*64)
NETWORK = VersionedAssetRef(assetType='NetworkPolicyRevision', assetId='n', revision=1, contentHash='b'*64)


def records(root):
    for case in CASES:
        body = {'identity': expected_identity(case, PROVIDER, NETWORK, 'agnes-2.5-flash', 'approved'),
                'status': 'completed', 'result': {'status': 'healthy', 'response_model': 'agnes-2.5-flash',
                'prompt_tokens': 10, 'completion_tokens': 3, 'total_tokens': 13, 'latency_ms': 10,
                'answer_present': True, 'response_contract_passed': True,
                'observed_at': (NOW-timedelta(hours=1)).isoformat()}}
        (root/(case[0]+'.json')).write_text(json.dumps(body))


def read(root, **kwargs):
    return read_verified_text_evidence(root, provider=PROVIDER, network=NETWORK,
        provider_model_id='agnes-2.5-flash', approval_ref='approved', checked_at=kwargs.get('checked_at', NOW))


def test_verified_evidence_keeps_original_time_and_stable_hash_without_bodies(tmp_path):
    records(tmp_path)
    first = read(tmp_path)
    second = read(tmp_path, checked_at=NOW+timedelta(minutes=1))
    assert first['sourceHash'] == second['sourceHash']
    assert len(first['cases']) == 3
    assert all(item['observedAt'] == (NOW-timedelta(hours=1)).isoformat() for item in first['cases'])
    text = json.dumps(first)
    for _, prompt, expected in CASES:
        assert prompt not in text and expected not in text


@pytest.mark.parametrize('change', ['missing','identity','identity_bool','unfinished','model','contract','boolean','tokens','time','future','stale','extra','oversized'])
def test_invalid_or_drifted_evidence_is_rejected(tmp_path, change):
    records(tmp_path)
    path = tmp_path/'instruction.json'
    body = json.loads(path.read_text())
    if change == 'missing': path.unlink()
    elif change == 'oversized': path.write_text(' '*20000)
    else:
        if change == 'identity': body['identity']['requestHash'] = 'f'*64
        if change == 'identity_bool': body['identity']['provider']['revision'] = True
        if change == 'unfinished': body['status'] = 'submitted'
        if change == 'model': body['result']['response_model'] = 'other'
        if change == 'contract': body['result']['response_contract_passed'] = False
        if change == 'boolean': body['result']['response_contract_passed'] = 1
        if change == 'tokens': body['result']['total_tokens'] = 12
        if change == 'time': body['result']['observed_at'] = '2026-09-11T03:00:00'
        if change == 'future': body['result']['observed_at'] = (NOW+timedelta(seconds=1)).isoformat()
        if change == 'stale': body['result']['observed_at'] = (NOW-timedelta(days=2)).isoformat()
        if change == 'extra': body['result']['answer'] = 'hidden-body'
        path.write_text(json.dumps(body))
    with pytest.raises(TextEvidenceBlocked): read(tmp_path)
