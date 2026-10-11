"""The successor validation entry never creates a key or grants publisher authority."""
import importlib
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[4]

@pytest.fixture
def profiles(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('build_ecommerce_qyh_successor_candidates'),importlib.import_module('validate_ecommerce_qyh_successor_signing')

def test_exact_new_profile_without_docker(profiles,monkeypatch):
    profile,validator=profiles;b=profile.load_builder()
    monkeypatch.setattr(b,'_docker',lambda *a,**k:pytest.fail('preflight invoked Docker'))
    r=b.preflight()
    assert {i['id']:i['version'] for i in r['bundles']}==validator.VERSIONS
    assert r['moduleCount']==8 and r['operationCount']==15
    assert b.STRIP_INHERITED_SIGNATURES is True

def test_missing_qualification_never_creates_state(profiles,tmp_path):
    _,v=profiles;state=tmp_path/'state'
    with pytest.raises(ValueError,match='QUALIFICATION_RECEIPT_REQUIRED'):
        v.validate_inputs(build=tmp_path/'build',build_receipt=tmp_path/'build.json',qualification_receipt=tmp_path/'absent.json',state=state)
    assert not state.exists()

def test_new_validation_has_no_sign_action_or_private_key_call(profiles):
    _,v=profiles;source=(ROOT/'scripts/validate_ecommerce_qyh_successor_signing.py').read_text()
    assert '.sign(' not in source and '._key(' not in source
    old=importlib.import_module('sign_ecommerce_qyh_recovery_candidates')
    assert old.VERSIONS['domain.ecommerce.core']=='1.4.3'
    assert v.VERSIONS['domain.ecommerce.core']=='1.4.4'

def test_generated_successor_sbom_passes_original_loader(profiles,tmp_path):
    import json
    from datetime import datetime,timezone
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    profile,_=profiles
    b=profile.load_builder(tmp_path)
    bundle=tmp_path/'domain.ecommerce.core'/'1.4.4'
    (bundle/'evidence').mkdir(parents=True)
    b._augment_sbom(bundle,sdk_hash='sha256:'+'a'*64,base_config_digest='sha256:'+'b'*64)
    payload=json.loads((bundle/'evidence/sbom.json').read_text())
    assert payload['bomFormat']=='CycloneDX'
    e=ManifestLoader._sbom_evidence('bundle://isolated/core', (bundle/'evidence/sbom.json').read_bytes(),datetime.now(timezone.utc))
    assert e.status.value=='valid'

QUALIFIED=ROOT/'.evidence/qyh-successor-qualification-20261012'

def test_actual_qualified_inputs_never_sign(profiles,tmp_path,monkeypatch):
    import json
    _,v=profiles
    signer=v.load_signer()
    monkeypatch.setattr(signer,'_key',lambda *a,**k:pytest.fail('private key accessed'))
    monkeypatch.setattr(signer,'sign',lambda *a,**k:pytest.fail('sign action invoked'))
    monkeypatch.setattr(v,'load_signer',lambda:signer)
    receipt=json.loads((QUALIFIED/'build-r2-receipt.json').read_text())
    state=tmp_path/'absent-state'
    result=v.validate_inputs(build=Path(receipt['output']),build_receipt=QUALIFIED/'build-r2-receipt.json',qualification_receipt=QUALIFIED/'qualification-r2-receipt.json',state=state)
    assert result['outcome']=='QYH_SUCCESSOR_SIGNING_INPUTS_VALID_NO_SIGN'
    assert result['publisherIdentityConnected'] is False and result['formalRuntimeReady'] is False
    assert not state.exists()

@pytest.mark.parametrize('mutation',['versions','heartbeat','buildHash','tamper'])
def test_actual_qualified_input_tamper_rejected(profiles,tmp_path,mutation):
    import json
    _,v=profiles
    q=json.loads((QUALIFIED/'qualification-r2-receipt.json').read_text())
    if mutation=='versions': q['resolved'][0]['version']='0.0.0'
    if mutation=='heartbeat': q['runtimeSessions']['domain.ecommerce.core']['heartbeatChecks']=2047
    if mutation=='buildHash': q['buildReceiptHash']='sha256:'+'0'*64
    if mutation=='tamper': q['tamperRejections'].pop()
    altered=tmp_path/'altered.json';altered.write_text(json.dumps(q))
    receipt=json.loads((QUALIFIED/'build-r2-receipt.json').read_text())
    state=tmp_path/'absent-state'
    with pytest.raises(ValueError,match='QUALIFICATION_RECEIPT_MISMATCH'):
        v.validate_inputs(build=Path(receipt['output']),build_receipt=QUALIFIED/'build-r2-receipt.json',qualification_receipt=altered,state=state)
    assert not state.exists()
