import importlib
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256

@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4]/'scripts'))
    p=importlib.import_module('a0v_bootstrap_successor_business')
    snapshot=dict(head=dict(installation_id=p.G_ID,etag_version=5,state='active',lock_hash=p.LOCK,overlay_revision='a0v-canonical-ecommerce-v1'),
        bindings=[dict(generation=p.G_GENERATION,revision=4,execution_epoch=3,enabled=True,operation_fence=False,desired_state='enabled',observed_state='ready',config_ref=deepcopy(p.CONFIG))],canaryInstallations=0)
    parent=dict(org_id='org-org',project_id='dev-project',receipt_id=p.DETACH,phase='detach',authority_data={'fixture':True},content_hash=canonical_sha256({'fixture':True}))
    return p,snapshot,parent

@pytest.mark.parametrize('fault',['installation','generation','revision','epoch','enabled','fence','config','canary','parent','hash'])
def test_exact_f_and_parent_drift_rejected(profile,fault):
    p,s,r=profile;b=s['bindings'][0]
    if fault=='installation':s['head']['installation_id']='old'
    elif fault=='generation':b['generation']='old'
    elif fault=='revision':b['revision']=5
    elif fault=='epoch':b['execution_epoch']=4
    elif fault=='enabled':b['enabled']=False
    elif fault=='fence':b['operation_fence']=True
    elif fault=='config':b['config_ref']['revision']=2
    elif fault=='canary':s['canaryInstallations']=1
    elif fault=='parent':r['receipt_id']='other'
    elif fault=='hash':r['content_hash']='sha256:'+'0'*64
    with pytest.raises(ValueError):p.request_from(s,r)


def test_unknown_intent_only_reads_never_registers(profile,monkeypatch,tmp_path):
    p,s,r=profile;monkeypatch.setattr(p,'STATE',tmp_path)
    request=p.request_from(s,r)
    import json
    (tmp_path/'register-intent.json').write_text(json.dumps(request.model_dump(mode='json',by_alias=True)))
    def forbidden(**kwargs):pytest.fail('unknown outcome must not submit again')
    plane=SimpleNamespace(first_dispatch_registration_service=SimpleNamespace(register_successor=forbidden,read_successor_receipt=lambda **kwargs:None))
    with pytest.raises(ValueError,match='readback'):p.register(plane,request)


def test_i_uses_post_detach_group_revision(profile):
    p,s,r=profile
    assert p.request_from(s,r).expectedGroupRevision==22
    assert p.KEY.endswith('generation-i-successor')
