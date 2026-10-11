import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[4]
@pytest.fixture
def entry(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('a0v_qyh_successor_installation')


def view(versions):
    return SimpleNamespace(scope=('org-org','dev-project'),installation_id='11111111-1111-4111-8111-111111111111',authorization='EVIDENCE_ONLY_NO_START',current_revision=4,etag_version=7,
        releases=tuple(SimpleNamespace(publisher='aos',bundle_id=k,version=v,content_hash='sha256:'+'a'*64) for k,v in versions.items()))


def test_new_profile_exact_and_original_unchanged(entry):
    old=importlib.import_module('a0v_qyh_restored_http')
    before=dict(old.SELECTED_VERSIONS)
    new=entry.load_entry()
    assert new.SELECTED_VERSIONS==entry.qualified.VERSIONS
    result=new.require_selected_installation(view(new.SELECTED_VERSIONS),installation_id='11111111-1111-4111-8111-111111111111')
    assert result['growthVersion']=='1.13.1' and result['apiStartAuthorized'] is False
    assert old.SELECTED_VERSIONS==before and old.SELECTED_VERSIONS['solution.ecommerce.growth']=='1.13.0'
    with pytest.raises(new.RestorationBlocked):new.require_selected_installation(view(before),installation_id='11111111-1111-4111-8111-111111111111')

@pytest.mark.parametrize('change',['hash','scope','duplicate'])
def test_selected_original_guard_or_qualified_hash_refuses(entry,change):
    v=view(entry.qualified.VERSIONS);expected={r.bundle_id:r.content_hash for r in v.releases}
    if change=='hash':v.releases[0].content_hash='sha256:'+'b'*64
    if change=='scope':v.scope=('dev-org','dev-project')
    if change=='duplicate':v.releases+=v.releases[:1]
    e=entry.load_entry()
    with pytest.raises((entry.SuccessorInstallationBlocked,e.RestorationBlocked)):
        result=e.require_selected_installation(v,installation_id=v.installation_id)
        entry.require_content_hashes(result,expected)


def test_actual_unsigned_qualified_tree_refused_before_identity(entry,monkeypatch,tmp_path):
    q=ROOT/'.evidence/qyh-successor-qualification-20261012'
    receipt=json.loads((q/'build-r2-receipt.json').read_text())
    monkeypatch.setattr(entry,'load_entry',lambda:pytest.fail('DB/identity entry before signed artifact check'))
    with pytest.raises(entry.SuccessorInstallationBlocked,match='SIGNED_ARTIFACT'):
        entry.run(build=Path(receipt['output']),build_receipt=q/'build-r2-receipt.json',qualification_receipt=q/'qualification-r2-receipt.json',signed_root=Path(receipt['output']),trust_roots_file=ROOT/'.evidence/qyh-full-system-restoration-20261011/restoration-public-trust-roots.json',identity_file=tmp_path/'absent',installation_id='11111111-1111-4111-8111-111111111111')

# The key and trust below are existing-material *test fixtures*, never real identity.
from test_qyh_existing_publisher_signing import case


def test_real_signed_four_artifacts_original_policy_and_exact_hashes(entry,case):
    signer,args,_,_=case
    result=signer.run(**args,sign=True)
    expected=json.loads(args['build_receipt'].read_text())['contentHashes']
    assert entry.signed_content_hashes(Path(result['signedTree']),args['trust_roots_file'],expected)==expected
    wrong=dict(expected);wrong['domain.ecommerce.core']='sha256:'+'b'*64
    with pytest.raises(entry.SuccessorInstallationBlocked):
        entry.signed_content_hashes(Path(result['signedTree']),args['trust_roots_file'],wrong)


def test_run_passes_original_installation_reader_then_exact_hash_gate(entry,case,monkeypatch):
    signer,args,_,_=case
    result=signer.run(**args,sign=True)
    expected=json.loads(args['build_receipt'].read_text())['contentHashes']
    original=entry.load_entry();called=[]
    def read(**kwargs):
        called.append(kwargs)
        v=view(entry.qualified.VERSIONS)
        for r in v.releases:r.content_hash=expected[r.bundle_id]
        return {'currentInstallation':original.require_selected_installation(v,installation_id=v.installation_id)}
    monkeypatch.setattr(original,'select_current_installation',read)
    monkeypatch.setattr(entry,'load_entry',lambda:original)
    kwargs=dict(build=args['build'],build_receipt=args['build_receipt'],qualification_receipt=args['qualification_receipt'],signed_root=Path(result['signedTree']),trust_roots_file=args['trust_roots_file'],identity_file=Path('/unused-isolated-fixture'),installation_id=view(entry.qualified.VERSIONS).installation_id)
    verified=entry.run(**kwargs)
    assert len(called)==1 and called[0]['installation_id']==kwargs['installation_id']
    assert verified['runtimeAuthorized'] is False and verified['formalIdentityVerified'] is False
    assert verified['currentInstallation']['apiStartAuthorized'] is False
