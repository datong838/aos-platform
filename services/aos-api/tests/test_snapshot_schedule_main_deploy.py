import importlib.util
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3]


def load():
    spec=importlib.util.spec_from_file_location('snapshot_main',ROOT/'scripts/a0v_snapshot_schedule_main_deploy.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def proof():
    return dict(outcome='SNAPSHOT_SCHEDULE_CLONE_RESTORE_VERIFIED',source='a0v_061',target='a0v_066',
        main='aos_meta_head',clone='aos_snapshot_schedule_20260916_test',migrations={'migration':'hash'},
        executors={'executor':'hash'},backup={'sha256':'backup'},before={'old':{'count':1,'digest':'a'}},
        after={'old':{'count':1,'digest':'a'}})


def test_exact_restored_proof_required():
    m=load();p=proof()
    m.validate_attestation(p,{'migration':'hash'},{'executor':'hash'},'backup')
    for key,value in [('source','a0v_060'),('clone','aos_meta_head'),('target','head'),
                      ('migrations',{}),('executors',{}),('after',{}),('before',{}),('backup',{'sha256':'other'})]:
        changed=deepcopy(p);changed[key]=value
        with pytest.raises(ValueError):m.validate_attestation(changed,{'migration':'hash'},{'executor':'hash'},'backup')


def test_main_profile_keeps_clone_guard_and_distinct_executor_binding():
    m=load();p=m.profile();c=m.clone.profile()
    assert p.TASK=='SC4-5L6Y6B-MAIN-MIGRATION-20260916'
    assert p.STATE!=c.STATE and p.CHAIN==c.CHAIN
    assert set(p.executor_hashes())==set(c.executor_hashes())|{'a0v_snapshot_schedule_main_deploy.py'}
    with pytest.raises(ValueError,match='clone only'):c.upgrade('aos_meta_head')


def test_existing_intent_is_readback_only(tmp_path,monkeypatch):
    from types import SimpleNamespace
    m=load();monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/'apply-intent.json').write_text('{}')
    p=SimpleNamespace(require_lease=lambda:None,upgrade=lambda *args:pytest.fail('must not upgrade'))
    monkeypatch.setattr(m,'profile',lambda:p)
    monkeypatch.setattr(m,'verify_clone',lambda p:None)
    monkeypatch.setattr(m,'backup_main',lambda p:pytest.fail('must not replace backup'))
    reads=[]
    monkeypatch.setattr(m,'readback',lambda p:reads.append(p) or {'readback':True})
    assert m.apply()=={'readback':True} and reads==[p]


def test_retained_backup_without_intent_requires_inspection(tmp_path,monkeypatch):
    from types import SimpleNamespace
    m=load();monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/'backup.json').write_text('{}')
    monkeypatch.setattr(m,'profile',lambda:SimpleNamespace(require_lease=lambda:None))
    monkeypatch.setattr(m,'verify_clone',lambda p:None)
    monkeypatch.setattr(m,'backup_main',lambda p:pytest.fail('must not overwrite'))
    with pytest.raises(ValueError,match='retained backup'):m.apply()
