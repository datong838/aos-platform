"""Existing publisher material fixtures are isolated and never grant real authority."""
import base64
import importlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from aos_api.asset_registry.canonical_json import canonical_sha256

ROOT = Path(__file__).resolve().parents[4]
QUALIFIED = ROOT / '.evidence/qyh-successor-qualification-20261012'

@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    module = importlib.import_module('sign_ecommerce_qyh_existing_publisher')
    key = Ed25519PrivateKey.generate()
    key_file = tmp_path / 'existing-key.pem'
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_file.chmod(0o600)
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    now = datetime.now(timezone.utc)
    root = {'publisher': 'aos', 'keyId': 'existing-qyh-isolated-test-fixture', 'algorithm': 'Ed25519',
        'publicKey': base64.b64encode(public).decode(), 'notBefore': (now-timedelta(minutes=5)).isoformat(),
        'notAfter': (now+timedelta(hours=1)).isoformat(), 'revokedAt': None}
    trust = tmp_path / 'existing-trust.json'
    def write_root():
        root.pop('revision', None)
        root['revision'] = canonical_sha256(root)
        trust.write_text(json.dumps({'trustRoots': [root]}))
    write_root()
    receipt = json.loads((QUALIFIED / 'build-r2-receipt.json').read_text())
    args = dict(build=Path(receipt['output']), build_receipt=QUALIFIED/'build-r2-receipt.json',
        qualification_receipt=QUALIFIED/'qualification-r2-receipt.json', state=tmp_path/'output',
        key_file=key_file, trust_roots_file=trust, key_id=root['keyId'])
    return module, args, root, write_root

def test_real_four_bundle_signatures_reuse_existing_material_only(case):
    m, args, _, _ = case
    before_key=args['key_file'].read_bytes();before_trust=args['trust_roots_file'].read_bytes()
    result=m.run(**args, sign=True)
    assert result['outcome']=='QYH_EXISTING_MATERIAL_SIGNED_ARTIFACTS_NO_PUBLICATION'
    assert result['formalIdentityVerified'] is False and result['registryPublishAuthorized'] is False
    assert len(list(Path(result['signedTree']).rglob('bundle.signature.json')))==4
    assert args['key_file'].read_bytes()==before_key and args['trust_roots_file'].read_bytes()==before_trust
    assert not list(args['state'].rglob('*.pem')) and not (args['state']/'trust-roots.json').exists()
    assert all(v==0 for v in result['effects'].values())

def test_default_validation_is_read_only(case):
    m,args,_,_=case
    result=m.run(**args)
    assert result['outcome']=='QYH_EXISTING_SIGNING_MATERIAL_MATCHED_NO_SIGN'
    assert not args['state'].exists()

@pytest.mark.parametrize('mutation', ['missingKey','publicMismatch','expired','revoked','widePermissions','symlink','localKeyId'])
def test_bad_material_rejected_before_output_creation(case,tmp_path,mutation):
    m,args,root,write_root=case
    if mutation=='missingKey': args['key_file'].unlink()
    if mutation=='publicMismatch': root['publicKey']=base64.b64encode(b'x'*32).decode();write_root()
    if mutation=='expired': root['notAfter']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();write_root()
    if mutation=='revoked': root['revokedAt']=datetime.now(timezone.utc).isoformat();write_root()
    if mutation=='widePermissions': args['key_file'].chmod(0o644)
    if mutation=='symlink':
        link=tmp_path/'key-link';link.symlink_to(args['key_file']);args['key_file']=link
    if mutation=='localKeyId': args['key_id']='a0v-local-qyh-core143-growth113-v1'
    with pytest.raises(m.PublisherSigningBlocked): m.run(**args,sign=True)
    assert not args['state'].exists()
    if mutation=='missingKey': assert not args['key_file'].exists()

def test_existing_output_never_overwritten(case):
    m,args,_,_=case;args['state'].mkdir();sentinel=args['state']/'keep';sentinel.write_text('original')
    with pytest.raises(m.PublisherSigningBlocked,match='OUTPUT_ALREADY_EXISTS'):
        m.run(**args,sign=True)
    assert sentinel.read_text()=='original'

def test_qualified_hash_tamper_denied_before_private_material_read(case,tmp_path,monkeypatch):
    m,args,_,_=case
    payload=json.loads(args['qualification_receipt'].read_text());payload['buildReceiptHash']='sha256:'+'0'*64
    altered=tmp_path/'altered.json';altered.write_text(json.dumps(payload));args['qualification_receipt']=altered
    monkeypatch.setattr(m,'existing_material',lambda **_:pytest.fail('key read before qualified-input rejection'))
    with pytest.raises(ValueError,match='QUALIFICATION_RECEIPT_MISMATCH'):m.run(**args,sign=True)
    assert not args['state'].exists()

def test_trust_changes_during_sign_leave_state_for_reconciliation(case,monkeypatch):
    m,args,root,write_root=case
    original=m.existing_material;calls=0
    def changing(**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:
            root['notAfter']=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat();write_root()
        return original(**kwargs)
    monkeypatch.setattr(m,'existing_material',changing)
    with pytest.raises(m.PublisherSigningBlocked,match='EXISTING_TRUST_CHANGED_DURING_SIGN'):
        m.run(**args,sign=True)
    assert (args['state']/'intent.json').exists()
    assert not (args['state']/'result.json').exists()
    with pytest.raises(m.PublisherSigningBlocked,match='OUTPUT_ALREADY_EXISTS'):
        m.run(**args,sign=True)

def test_existing_trust_symlink_is_not_followed(case,tmp_path):
    m,args,_,_=case
    link=tmp_path/'trust-link';link.symlink_to(args['trust_roots_file']);args['trust_roots_file']=link
    with pytest.raises(m.PublisherSigningBlocked,match='EXISTING_PUBLISHER_MATERIAL_UNAVAILABLE'):
        m.run(**args,sign=True)
    assert not args['state'].exists()
