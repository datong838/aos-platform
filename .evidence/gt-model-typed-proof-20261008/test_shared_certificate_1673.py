"""Synthetic pure fixtures distinguish cryptography from persisted authority."""
from pathlib import Path
import copy, json, base64
from datetime import datetime, timedelta
import pytest
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.aip_model_eval_execution_contracts import (
    canonical_shared_parent_certificate_signing_bytes as canonical,
    validate_shared_parent_certificate_signature as verify,
    canonical_model_certificate_signing_bytes,
    canonical_original_target_certificate_signing_bytes)
from shared_certificate_fixture_1673 import keys_for_manifest, issue

@pytest.fixture
def fixture():
    root = Path(__file__).resolve().parents[1]
    d = json.loads((root/'gt-atomic-model-admission-20261008/shared-risk-description-native-1672-r6/native-description-proof.json').read_text())['description']
    d = copy.deepcopy(d)
    keys = keys_for_manifest(d['immutable']['manifest'])
    d['immutable']['manifestHash'] = canonical_hash(d['immutable']['manifest'])
    d['contentHash'] = 'sha256:' + canonical_hash(d['immutable'])
    end = datetime.fromisoformat(d['immutable']['manifest']['judgeRequest']['expiresAt'])
    t = end - timedelta(seconds=10)
    return d, issue(d, keys, t), t


def test_four_leg_real_signatures_and_separate_domain(fixture):
    d, proof, t = fixture
    assert len(proof['certificates']) == 4
    assert not proof['root_provenance_verified'] and not proof['execution_allowed']
    for e in proof['certificates']:
        assert canonical(d, e['certificate']).startswith(b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n')
        for old in (canonical_model_certificate_signing_bytes, canonical_original_target_certificate_signing_bytes):
            with pytest.raises(ValueError): old(d['immutable']['manifest'], e['certificate'])

@pytest.mark.parametrize('field', ['descriptionHash','originalRiskHash','callerXid','callerPid','requestHash','manifestHash','caseId','executionId','candidateRef','leg'])
def test_exact_claim_drift(fixture, field):
    d, p, t = fixture; c = copy.deepcopy(p['certificates'][0]['certificate'])
    if field.endswith('Hash'): c[field] = ('sha256:' if field in ('descriptionHash','originalRiskHash') else '')+'a'*64
    elif field == 'callerPid': c[field] += 1
    elif field == 'callerXid': c[field] = str(int(c[field])+1)
    elif field == 'candidateRef': c[field]['assetId'] += '-drift'
    elif field == 'leg': c[field]['intentRef']['resourceId'] += '-drift'
    else: c[field] += '-drift'
    with pytest.raises(ValueError): canonical(d, c)

@pytest.mark.parametrize('field', ['identityId','intentRef','jointReceiptRef'])
def test_rehashed_whole_description_cannot_reuse_certificate(fixture, field):
    d, p, t = fixture; d = copy.deepcopy(d)
    leg = d['immutable']['manifest']['cases'][0]['target']
    if field == 'identityId': leg[field] += '-drift'
    else: leg[field]['resourceId'] += '-drift'
    d['immutable']['manifestHash'] = canonical_hash(d['immutable']['manifest'])
    d['contentHash'] = 'sha256:' + canonical_hash(d['immutable'])
    with pytest.raises(ValueError): canonical(d, p['certificates'][0]['certificate'])

@pytest.mark.parametrize('fault', ['signature','root_key','root_id','expired','revoked_root','revoked_identity','mutable_revocations','bool_pid','old_schema','judge_governance_hash'])
def test_signature_time_and_typed_negatives(fixture, fault):
    d, p, t = fixture; e = copy.deepcopy(p['certificates'][1]); r = copy.deepcopy(p['presented_root']); revoked = frozenset()
    if fault == 'signature': e['signatureBase64'] = base64.b64encode(bytes(64)).decode()
    elif fault == 'root_key': r['publicKeyBase64'] = base64.b64encode(bytes(32)).decode()
    elif fault == 'root_id': r['issuerId'] += '-wrong'
    elif fault == 'expired': t = datetime.fromisoformat(e['certificate']['validUntil'])
    elif fault == 'revoked_root': r['revokedAt'] = t.isoformat()
    elif fault == 'revoked_identity': revoked = frozenset([e['certificate']['leg']['identityId']])
    elif fault == 'mutable_revocations': revoked = set()
    elif fault == 'bool_pid': e['certificate']['callerPid'] = True
    elif fault == 'old_schema': e['certificate']['schemaVersion'] = 'aos.model-eval-executor-certificate-signing-input/v1'
    elif fault == 'judge_governance_hash': e['certificate']['requestHash'] = d['immutable']['manifest']['judgeRequest']['judgeGovernanceApplication']['requestHash']
    with pytest.raises(ValueError): verify(d, e, issuer_input=r, checked_at=t, revoked_identity_ids=revoked)
