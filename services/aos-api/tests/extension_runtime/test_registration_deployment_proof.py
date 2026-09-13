import importlib.util
import json
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
import a0v_registration_deploy as deploy


@pytest.fixture
def proof(tmp_path,monkeypatch):
    monkeypatch.setattr(deploy,'STATE',tmp_path)
    monkeypatch.setattr(deploy.base,'migration_hashes',lambda:{'migration':'sha256:expected'})
    backup=tmp_path/'aos_meta_head-before-a0v_030.dump';backup.write_bytes(b'protected-backup')
    return dict(outcome='REGISTRATION_CLONE_VERIFIED',source=deploy.SOURCE,target=deploy.TARGET,
        main=deploy.base.MAIN,clone=deploy.CLONE,migrations=deploy.base.migration_hashes(),
        backup=dict(path=str(backup),sha256=deploy.base.digest(backup)),before={'rows':0},after={'rows':0})


@pytest.mark.parametrize('change',['target','source','clone','main','migrations','backup-path','backup-bytes','data'])
def test_altered_proof_cannot_authorize_main_migration(proof,change):
    if change in ('target','source','clone','main'):proof[change]='other'
    elif change=='migrations':proof['migrations']={}
    elif change=='backup-path':proof['backup']['path']='/tmp/other.dump'
    elif change=='backup-bytes':Path(proof['backup']['path']).write_bytes(b'changed')
    else:proof['after']={'rows':1}
    with pytest.raises(ValueError):deploy.validate_proof(proof)


def test_verified_proof_is_read_only(proof):
    before=json.dumps(proof,sort_keys=True)
    deploy.validate_proof(proof)
    assert json.dumps(proof,sort_keys=True)==before


def test_unknown_apply_intent_blocks_before_opening_database(tmp_path,monkeypatch):
    monkeypatch.setattr(deploy,'STATE',tmp_path);monkeypatch.setattr(deploy,'require_lease',lambda:None)
    (tmp_path/'apply-intent.json').write_text('{}')
    monkeypatch.setattr(deploy.base,'connect',lambda *a,**k:pytest.fail('must not open database'))
    with pytest.raises(ValueError,match='readback'):deploy.apply()


def test_main_identity_proof_never_overwrites_clone_proof(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from aos_api import ecommerce_growth_registration_connection as connection
    from aos_api.asset_registry import control_wiring
    monkeypatch.setattr(deploy,'STATE',tmp_path)
    (tmp_path/'identity-clone.json').write_text('retained clone proof')
    @contextmanager
    def connect():yield SimpleNamespace(info=SimpleNamespace(dbname=deploy.base.MAIN))
    def status(**kw):
        if kw['scope'].org_id=='dev-org' or kw['actor']=='user:dev':raise PermissionError('denied')
        return dict(state='unregistered',allowedActions=[])
    monkeypatch.setattr(connection,'registration_connection',connect)
    monkeypatch.setattr(control_wiring,'build_runtime_control_plane',lambda **kw:SimpleNamespace(first_dispatch_registration_service=SimpleNamespace(registration_status=status)))
    deploy.verify_identity_target(tmp_path/'private-reference',deploy.base.MAIN,'identity-main.json')
    assert (tmp_path/'identity-clone.json').read_text()=='retained clone proof'
    assert json.loads((tmp_path/'identity-main.json').read_text())['database']==deploy.base.MAIN
