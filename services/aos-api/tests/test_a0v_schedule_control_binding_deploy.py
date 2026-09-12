"""Deployment fail-closed checks; no real database or source access here."""
import importlib.util
import json
from pathlib import Path
import pytest


@pytest.fixture
def deploy(monkeypatch):
    root=Path(__file__).resolve().parents[3]
    spec=importlib.util.spec_from_file_location('controlled_claim_deploy_test',root/'scripts/a0v_schedule_control_binding_deploy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'require_leases',lambda:None)
    return module


def test_retained_backup_is_never_overwritten(deploy,tmp_path,monkeypatch):
    monkeypatch.setattr(deploy,'STATE',tmp_path)
    backup=tmp_path/'aos_meta_head-before-a0v_025.dump'
    backup.write_bytes(b'retained proof')
    monkeypatch.setattr(deploy,'connect',lambda *a,**kw:pytest.fail('must reject before connecting'))
    with pytest.raises(ValueError,match='never overwritten'):deploy.prepare()
    assert backup.read_bytes()==b'retained proof'


@pytest.mark.parametrize('field',['migrations','backup'])
def test_changed_migration_or_backup_cannot_reach_database(deploy,tmp_path,monkeypatch,field):
    monkeypatch.setattr(deploy,'STATE',tmp_path)
    backup=tmp_path/'retained.dump';backup.write_bytes(b'original')
    proof={'outcome':'ISOLATED_RESTORE_AND_MIGRATION_VERIFIED','main':deploy.MAIN,'clone':deploy.CLONE,
        'migrations':deploy.migration_hashes(),'backup':{'path':str(backup),'sha256':deploy.digest(backup)}}
    if field=='migrations':proof['migrations']={}
    else:backup.write_bytes(b'changed')
    (tmp_path/'prepare.json').write_text(json.dumps(proof))
    monkeypatch.setattr(deploy,'connect',lambda *a,**kw:pytest.fail('must reject before connecting'))
    with pytest.raises(ValueError,match='evidence differs'):deploy.apply()


def test_unknown_database_rejected_before_credential_loading(deploy):
    with pytest.raises(ValueError,match='unexpected database'):deploy.parameters('postgres')


def test_expired_lease_prevents_environment_work(deploy,tmp_path,monkeypatch):
    # Load the actual validator, not the fixture replacement.
    spec=importlib.util.spec_from_file_location('controlled_claim_lease_test',Path(deploy.__file__))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/'repo';root.mkdir()
    folder=tmp_path/'docs/palantier/AOS项目开发上下文/memory';folder.mkdir(parents=True)
    (folder/'leases.json').write_text(json.dumps({'leases':[{'task_id':'A0V-SCHEDULE-BINDING-LOCAL-MIGRATION-20260913',
        'owner':'m1','status':'ACTIVE','lease_expires_at':'2000-01-01T00:00:00+00:00'}]}))
    monkeypatch.setattr(module,'ROOT',root)
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**kw:pytest.fail('expired lease must reject first'))
    with pytest.raises(ValueError,match='lease unavailable'):module.require_leases()
